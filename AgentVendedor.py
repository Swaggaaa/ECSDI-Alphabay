# -*- coding: utf-8 -*-
"""
Ejemplo de agente para implementar los vuestros.

@author: Swaggaaa
"""

from __future__ import print_function

import random
from multiprocessing import Process, Queue
import socket

from rdflib import Namespace, Graph, RDF, URIRef, Literal
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
import AgentUtil.SPARQLHelper
from models.Pedido import Pedido

__author__ = 'Swaggaaa'

# Contador de mensajes
mss_cnt = 0

# Global triplestore graph
dsgraph = Graph()

logger = config_logger(level=1)

cola1 = Queue()

# Flask stuff
app = Flask(__name__)


@app.route("/comm")
def comunicacion():
    global dsgraph
    global mss_cnt
    global best_offer
    global num_respuestas

    message = request.args['content']
    gm = Graph()
    gm.parse(data=message)
    gr = None

    msgdic = get_message_properties(gm)
    if msgdic is None:
        gr = build_message(Graph(), ACL['not-understood'], sender=AgentUtil.Agents.AgenteCentroLogistico.uri,
                           msgcnt=mss_cnt)
    else:
        perf = msgdic['performative']

        # Se nos solicita que enviemos los lotes de cierta prioridad
        if perf == ACL.inform:
            if 'content' in msgdic:
                content = msgdic['content']

                if 'notificar-envios' in str(content):
                    ids = gm.value(subject=content, predicate=AB.formado_por)
                    transportista = gm.value(subject=content, predicate=AB.transportista)

                    for id in ids:
                        notificar_usuario(id, transportista)

            else:
                gr = build_message(Graph(), ACL['not-understood'], sender=AgentUtil.Agents.AgenteCentroLogistico.uri,
                                   msgcnt=mss_cnt)
        else:
            gr = build_message(Graph(), ACL['not-understood'], sender=AgentUtil.Agents.AgenteCentroLogistico.uri,
                               msgcnt=mss_cnt)

    mss_cnt += 1
    return gr.serialize(format='xml')


def notificar_usuario(id, transportista):
    query = """
       prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
       
       SELECT ?fecha_compra ?prioridad
       WHERE {
            ?Pedido ab:fecha_compra ?fecha_compra .
            ?Pedido ab:id ?id .
            ?Pedido ab:prioridad ?prioridad .
            FILTER (?id = %s) }
    """ % id

    res = AgentUtil.SPARQLHelper.read_query(query)

    fecha_compra = res["results"]["bindings"][0]["fecha_compra"]["value"]
    prioridad = res["results"]["bindings"][0]["prioridad"]["value"]
    fecha_entrega = fecha_compra

    query = """
   prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
   
   INSERT DATA {
        ab:Pedido%(id)s ab:fecha_entrega %(fecha)s .
        ab:Pedido%(id)s ab:es_entregado_por %(transportista)s .
        }
    """ % {'id': id, 'fecha': fecha_entrega, 'transportista': transportista}

    res = AgentUtil.SPARQLHelper.read_query(query)


@app.route("/buy", methods=['POST'])
def browser_search():
    global dsgraph
    query = """
           prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>

          SELECT ?n_ref (SAMPLE(?id) AS ?n_ref_id) (SAMPLE(?nombre) AS ?n_ref_nombre) (SAMPLE(?modelo) AS ?n_ref_modelo)
         (SAMPLE(?calidad) AS ?n_ref_calidad) (SAMPLE(?precio) AS ?n_ref_precio)
          WHERE 
          {
              %s
              ?Producto ab:id ?id.
              ?Producto ab:n_ref ?n_ref.
              ?Producto ab:nombre ?nombre.
              ?Producto ab:modelo ?modelo.
              ?Producto ab:calidad ?calidad.
              ?Producto ab:precio ?precio
            }
            """ % AgentUtil.SPARQLHelper.filterSPARQLValues("?id", request.form.getlist('items'), False)

    res = AgentUtil.SPARQLHelper.read_query(query)
    return render_template('buy.html', products=res)


@app.route("/purchase", methods=['GET', 'POST'])
def browser_purchase():
    if request.method == 'POST':
        global mss_cnt
        peso_total = 0.0
        query = """
        prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
             
        SELECT ?id ?peso
        WHERE
        {
          %s
          ?Producto ab:id ?id .
          ?Producto ab:peso ?peso .
          }
          """ % AgentUtil.SPARQLHelper.filterSPARQLValues("?id", request.form['items'], False)

        res = AgentUtil.SPARQLHelper.read_query(query)

        pedido = Pedido()
        pedido.id = random.randint(1, 99999999)  # TODO: Get latest id
        pedido.prioridad = request.form['prioridad']
        pedido.fecha_compra = time.strftime("%d/%m/%Y")
        pedido.direccion = request.form['direccion']
        pedido.ciudad = request.form['ciudad']

        for item in request.form['items']:
            pedido.compuesto_por.append(item)

        for p in res["results"]["bindings"]:
            peso_total += float(p["peso"]["value"])

        pedido.peso_total = peso_total

        query = """
        
        prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
             
        INSERT DATA {
             ab:Pedido%(id)s rdf:type ab:Pedido .
             ab:Pedido%(id)s ab:id %(id)s .
             ab:Pedido%(id)s ab:prioridad '%(prioridad)s' .
             ab:Pedido%(id)s ab:fecha_compra '%(fecha)s' .
             ab:Pedido%(id)s ab:direccion '%(dir)s' .
             ab:Pedido%(id)s ab:ciudad '%(ciudad)s' .
             ab:Pedido%(id)s ab:peso_total %(peso)s .
             ab:Pedido%(id)s ab:comprado_por '%(usuario)s' .
        """ % {'id': pedido.id, 'prioridad': pedido.prioridad, 'fecha': pedido.fecha_compra, 'dir': pedido.direccion,
               'ciudad': pedido.ciudad, 'peso': pedido.peso_total, 'usuario': request.cookies.get('username')}

        for item in pedido.compuesto_por:
            query += "ab:pedido%(id)s ab:compuesto_por %(item)s" % {'id': pedido.id, 'item': item}

        res = AgentUtil.SPARQLHelper.update_query(query)

        gmess = Graph()
        gmess.bind('ab', AB)
        content = AB[AgentUtil.Agents.AgenteVendedor.name + '-preparar-pedido']
        gmess.add((content, RDF.type, AB.Pedido))
        gmess.add((content, AB.id, Literal(pedido.id)))
        gmess.add((content, AB.prioridad, Literal(pedido.prioridad)))
        gmess.add((content, AB.fecha_compra, Literal(pedido.fecha_compra)))
        gmess.add((content, AB.direccion, Literal(pedido.direccion)))
        gmess.add((content, AB.ciudad, Literal(pedido.ciudad)))
        for item in pedido.compuesto_por:
            gmess.add((content, AB.compuesto_por, Literal(item)))

        gmess.add((content, AB.peso_total, peso_total))
        msg = build_message(gmess, perf=ACL.inform,
                            sender=AgentUtil.Agents.AgenteVendedor.uri,
                            receiver=AgentUtil.Agents.AgenteCentroLogistico.uri,
                            content=content,
                            msgcnt=mss_cnt)
        send_message(msg, AgentUtil.Agents.AgenteCentroLogistico.address)
        mss_cnt += 1

        render_template('finished.html', products=res)


@app.route("/refund", methods=['GET', 'POST'])
def browser_refund():
    global dsgraph
    if request.method == 'GET':
        query = """
                           prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>

                          SELECT ?n_ref (SAMPLE(?nombre) AS ?n_ref_nombre) 
                                        (SAMPLE(?modelo) AS ?n_ref_modelo) 
                                        (SAMPLE(?precio) AS ?n_ref_precio) 
                                        (COUNT(*) AS ?cantidad)
                          WHERE 
                          {
                              ?Producto ab:n_ref ?n_ref.
                              ?Producto ab:nombre ?nombre.
                              ?Producto ab:modelo ?modelo.
                              ?Producto ab:precio ?precio.
                              ?Producto ab:comprado_por ?comprado_por.
                          """
        # TODO: Cambiar Elena por el nombre de usuario
        query += "FILTER regex (str(?comprado_por), 'Elena')."
        query += "} GROUP BY ?n_ref"

        res = AgentUtil.SPARQLHelper.read_query(query)

        try:
            res["results"]["bindings"][0]["n_ref"]
        except KeyError:
            del res["results"]["bindings"][0]

        return render_template("refund.html", products=res, host_vendedor=(
                AgentUtil.Agents.hostname + ':' + str(AgentUtil.Agents.VENDEDOR_PORT)))

    else:
        if request.form["motivo"] != 'Not satisfied':
            return render_template("resolution.html", resolution="Your request have been accepted", host_vendedor=(
                    AgentUtil.Agents.hostname + ':' + str(AgentUtil.Agents.VENDEDOR_PORT)
            ))


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
    # Ponemos en marcha los behaviors y pasamos la cola para transmitir información
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=AgentUtil.Agents.hostname, port=AgentUtil.Agents.VENDEDOR_PORT)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')
