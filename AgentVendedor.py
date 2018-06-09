# -*- coding: utf-8 -*-
"""
@author: Swaggaaa
"""

from __future__ import print_function
from multiprocessing import Process, Queue
import socket

from rdflib import Namespace, Graph, RDF, URIRef, Literal
from flask import Flask, request, render_template
import SPARQLWrapper
from rdflib.namespace import FOAF
import random
import AgentUtil
from AgentUtil.ACLMessages import build_message, send_message
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Agent import Agent
from AgentUtil.Logging import config_logger
import AgentUtil.Agents
from datetime import datetime, date, time, timedelta
import calendar

# Para el sleep
import time

from AgentUtil.OntoNamespaces import ACL, AB
from AgentUtil.SPARQLHelper import filterSPARQLValues

__author__ = 'Swaggaaa'

# Contador de mensajes
mss_cnt = 0

# Global triplestore graph
dsgraph = Graph()

sparql = SPARQLWrapper.SPARQLWrapper(AgentUtil.Agents.endpoint)

logger = config_logger(level=1)

cola1 = Queue()

# Flask stuff
app = Flask(__name__)


@app.route("/buy", methods=['POST'])
def browser_search():
    global dsgraph
    query = """
           prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>

SELECT ?n_ref (SAMPLE(?nombre) AS ?n_ref_nombre) (SAMPLE(?modelo) AS ?n_ref_modelo) (SAMPLE(?calidad) AS ?n_ref_calidad) (SAMPLE(?precio) AS ?n_ref_precio) (COUNT(*) AS ?disponibilidad)
          WHERE 
          {   
              %s  
              ?Producto ab:n_ref ?n_ref.
              ?Producto ab:nombre ?nombre.
              ?Producto ab:modelo ?modelo.
              ?Producto ab:calidad ?calidad.
              ?Producto ab:precio ?precio
            }
            GROUP BY (?n_ref)
            """ % filterSPARQLValues("?n_ref", request.form.getlist('items'), False)

    sparql.setQuery(query)
    res = sparql.query().convert()
    return render_template('buy.html', products=res)


@app.route("/purchase", methods=['POST'])
def browser_purchase():
    global mss_cnt
    gmess = Graph()
    gmess.bind('ab', AB)
    content = AB[AgentUtil.Agents.AgenteVendedor.name + '-preparar-pedido']
    gmess.add((content, RDF.type, AB.Pedido))
    gmess.add((content, AB.id, Literal(123)))  # TODO: Hacer consulta para saber el ultimo id
    gmess.add((content, AB.prioridad, Literal(request.form['prioridad'])))
    gmess.add((content, AB.fecha_compra, Literal(time.strftime("%d/%m/%Y"))))
    gmess.add((content, AB.direccion, Literal(request.form['direccion'])))
    gmess.add((content, AB.compuesto_por, Literal(AB['Sneakers_Nike'])))
    gmess.add((content, AB.compuesto_por, Literal(AB["Levi's_Jeans_1"])))
    msg = build_message(gmess, perf=ACL.inform,
                        sender=AgentUtil.Agents.AgenteVendedor.uri,
                        receiver=AgentUtil.Agents.AgenteCentroLogistico.uri,
                        content=content,
                        msgcnt=mss_cnt)
    send_message(msg, AgentUtil.Agents.AgenteCentroLogistico.address)
    mss_cnt += 1


@app.route("/refund", methods=['GET', 'POST'])
def browser_refund():
    global dsgraph
    if request.method == 'GET':
        query = """
                           prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>

                          SELECT ?compuesto_por
                          WHERE 
                          {
                              ?Pedido ab:comprado_por ?comprado_por.
                              ?Pedido ab:compuesto_por ?compuesto_por.
                             
                          """
        #TODO: Cambiar Elena por el nombre de usuario
        query += "FILTER regex (str(?comprado_por), 'Elena').}"

        sparql.setQuery(query)
        res = sparql.query().convert()
        refs = []

        for ref in res["results"]["bindings"]:
            refs.append(ref['compuesto_por']['value'])

        query = """
                           prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
        
                          SELECT ?id ?n_ref ?nombre ?modelo ?precio 
                          WHERE 
                          {
                                %s
                              ?Producto ab:id ?id.
                              ?Producto ab:n_ref ?n_ref.
                              ?Producto ab:nombre ?nombre.
                              ?Producto ab:modelo ?modelo.
                              ?Producto ab:precio ?precio.
                              
                          
        } """ % filterSPARQLValues("?id", refs, False)

        sparql.setQuery(query)
        res = sparql.query().convert()

        return render_template("refund.html", products=res, host_vendedor=(
                AgentUtil.Agents.hostname + ':' + str(AgentUtil.Agents.VENDEDOR_PORT)))

    else:


        if request.form["motivo"] != 'Not satisfied':
            query = """
                 prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
                 
                        DELETE {?Producto ab:comprado_por 'Elena'}
                        WHERE {?Producto ab:id request.form['item']}  """
            #TODO: Cambiar Elena por el nombre de usuario

            sparql.setQuery(query)

            return render_template("resolution.html", resolution="Your request has been accepted. The transport company in charge of the devoution is %s" %escoger_transportista(), host_vendedor=(
                AgentUtil.Agents.hostname + ':' + str(AgentUtil.Agents.VENDEDOR_PORT)
            ))

        else:
            fecha_actual = datetime.now()

            query =  """
                prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
                
                SELECT ?fecha_entrega
                WHERE{
                    ?Pedido ab:fecha_entrega ?fecha_entrega .
                    ?Pedido ab:compuesto_por ?compuesto_por .
                    """
            query += "FILTER regex (str(?compuesto_por), '%s')." % request.form['item']
            query += "}"

            sparql.setQuery(query)
            res = sparql.query().convert()

            fecha_entrega = res["results"]["bindings"][0]["fecha_entrega"]["value"]
            fecha_entrega = datetime.strptime(fecha_entrega,   "%Y-%m-%d %H:%M:%S.%f")
            dias_pasados= fecha_actual - fecha_entrega

            if dias_pasados.days <= 15:
                return render_template("resolution.html",
                                       resolution="Your request has been accepted. The transport company in charge of the devoution is %s" % escoger_transportista(),
                                       host_vendedor=(
                                               AgentUtil.Agents.hostname + ':' + str(AgentUtil.Agents.VENDEDOR_PORT)
                                       ))
            else:
                return render_template("resolution.html",
                                        resolution="Your request has not been accepted because it has been %s days since you have received the product" %dias_pasados.days,
                                        host_vendedor=(
                        AgentUtil.Agents.hostname + ':' + str(AgentUtil.Agents.VENDEDOR_PORT)
                ))



def escoger_transportista():
    query = """
            prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>

                    SELECT ?transportista
                    WHERE {?Empresa_de_transporte ab:transportista ?transportista }"""

    sparql.setQuery(query)
    res = sparql.query().convert()

    i = random.randint(0, AgentUtil.Agents.NUM_TRANSPORTISTAS)
    transportista = res["results"]["bindings"][i-1]["transportista"]["value"]
    return transportista



# Aqui se recibiran todos los mensajes. A diferencia de una API Rest (como hacemos en ASW o PES), aqui hay solo 1
# única ruta, y luego filtramos por el contenido de los mensajes y las órdenes que contengan
@app.route("/comm")
def comunicacion():
    global dsgraph
    global mss_cnt
    pass


# Para parar el agente. Por ahora no lo necesitaremos ya que se supone que están activos 24/7 skrra
@app.route("/Stop")
def stop():
    tidyup()
    shutdown_server()
    return "Parando Servidor"


# Se hacen limpiezas en caso que tuvieramos handles, conexiones o lo que sea abierto que debe ser liberado
def tidyup():
    pass


# Esta función se ejecuta en bucle (a no ser que lo cambiéis) y es el comportamiento inicial del agente. Aquí podéis
# mandar mensajes a los demás o hacer el trabajo que no requiera la petición de un agente
def agentbehavior1(cola):
    graph = cola.get()
    while True:
        time.sleep(1)
        pass

    pass


if __name__ == '__main__':
    # Nos conectamos al StarDog
    sparql.setCredentials(user='admin', passwd='admin')
    sparql.setReturnFormat(SPARQLWrapper.JSON)

    # Ponemos en marcha los behaviors y pasamos la cola para transmitir información
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=AgentUtil.Agents.hostname, port=AgentUtil.Agents.VENDEDOR_PORT)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')
