# -*- coding: utf-8 -*-
"""
Ejemplo de agente para implementar los vuestros.

@author: Swaggaaa
"""

from __future__ import print_function
from multiprocessing import Process, Queue
import socket

from rdflib import Namespace, Graph, RDF, URIRef, Literal
from rdflib import Namespace, Graph, RDF, URIRef
from flask import Flask, request, render_template
import SPARQLWrapper
from rdflib.namespace import FOAF

import AgentUtil
from AgentUtil.ACLMessages import build_message, send_message, get_message_properties
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Agent import Agent
from AgentUtil.Logging import config_logger
import AgentUtil.Agents

# Para el sleep
import time

from AgentUtil.OntoNamespaces import ACL, AB
from AgentUtil.SPARQLHelper import filterSPARQLValues
from models.Producto import Producto

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

    msg = build_message(gmess, perf=ACL.inform,
                        sender=AgentUtil.Agents.AgenteVendedor.uri,
                        receiver=AgentUtil.Agents.AgenteCentroLogistico.uri,
                        msgcnt=mss_cnt)
    gr = send_message(msg, AgentUtil.Agents.AgenteCentroLogistico.address)
    mss_cnt += 1
    return gr


# Aqui se recibiran todos los mensajes. A diferencia de una API Rest (como hacemos en ASW o PES), aqui hay solo 1
# única ruta, y luego filtramos por el contenido de los mensajes y las órdenes que contengan
@app.route("/comm")
def comunicacion():
    global dsgraph
    global mss_cnt

    message = request.args['content']
    gm = Graph()
    gm.parse(data=message)

    msgdic = get_message_properties(gm)
    if msgdic is None:
        gr = build_message(Graph(), ACL['not-understood'], sender=AgentUtil.Agents.AgenteCentroLogistico.uri,
                           msgcnt=mss_cnt)
    else:
        perf = msgdic['performative']

        if perf != ACL.inform:
            gr = build_message(Graph(), ACL['not-understood'], sender=AgentUtil.Agents.AgenteCentroLogistico.uri,
                               msgcnt=mss_cnt)
        else:
            if 'content' in msgdic:
                content = msgdic['content']
                producto = Producto()
                producto.id = gm.value(subject=content, predicate=AB.id)
                producto.prioridad = gm.value(subject=content, predicate=AB.prioridad)
                producto.fecha_compra = gm.value(subject=content, predicate=AB.direccion)
                producto.compuesto_por = gm.value(subject=content, predicate=AB.compuesto_por)

                prepare_shipping(producto)

            gr = build_message(Graph(),
                               ACL['inform-done'],
                               sender=AgentUtil.Agents.AgenteCentroLogistico.uri,
                               msgcnt=mss_cnt,
                               receiver=msgdic['sender'], )

            oferta = solicita_oferta()
            # TODO: Negociacion
            aceptar_oferta(oferta)

    mss_cnt += 1
    return gr.serialize(format='xml')


def prepare_shipping(producto):
    query = """
 prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
           
           SELECT ?Lote ?id
           WHERE
            {
           ?Lote rdf:type ab:Lote .
           ?Lote ab:id ?id
            }
           """
    sparql.setQuery(query)
    res = sparql.query().convert()

    if len(res["results"]["bindings"]) == 0:  # TODO: Valores reales
        query = """
         prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
           
           INSERT DATA {
           ab:Lote%(loteid)s rdf:type ab:Lote .
           ab:Lote%(loteid)s ab:id %(id)d .
           ab:Lote%(loteid)s ab:peso %(peso)f .
           ab:Lote%(loteid)s ab:volumen %(vol)f .
           ab:Lote%(loteid)s ab:ciudad_destino %(ciudad)s .
           ab:Lote%(loteid)s ab:formado_por %(uriProducto)s .}
           """ % {'loteid': 1, 'id': 1, 'peso': 13.7, 'vol': 5.2, 'ciudad': 'Lloret', 'uriProducto': 'urifakeuri'}
        sparql.setQuery(query)
        sparql.query()  # Creamos un nuevo lote con el pedido
    else:
        query = """
        prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
           
           INSERT DATA {
           ab:Lote%(loteid)s ab:formado_por %(uriProducto)s .}
        """ % {'loteid': res["results"]["bindings"][0]["id"]["value"], 'uriProducto': 'urifakeuri'}
        sparql.setQuery(query)
        sparql.query()  # Insertamos el nuevo producto en el lote elegido


def solicita_oferta():
    global mss_cnt
    gmess = Graph()
    gmess.bind('ab', AB)
    msg = build_message(gmess, perf=ACL.request,
                        sender=AgentUtil.Agents.AgenteCentroLogistico.uri,
                        receiver=AgentUtil.Agents.AgenteTransportista.uri,
                        msgcnt=mss_cnt)
    res = send_message(msg, AgentUtil.Agents.AgenteTransportista.address)
    message = get_message_properties(res)
    mss_cnt += 1

    return message


def aceptar_oferta(oferta):
    global mss_cont
    gmess = Graph()
    gmess.bind('ab', AB)
    msg = build_message(gmess, perf=ACL.accept - proposal,
                        sender=AgentUtil.Agents.AgenteCentroLogistico.uri,
                        receiver=AgentUtil.Agents.AgenteTransportista.uri,
                        msgcnt=mss_cnt)
    res = send_message(msg, AgentUtil.Agents.AgenteTransportista.address)
    mss_cnt += 1


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
    app.run(host=AgentUtil.Agents.hostname, port=AgentUtil.Agents.CENTROLOG_PORT)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')
