# -*- coding: utf-8 -*-

from __future__ import print_function
from multiprocessing import Process, Queue
import socket

from rdflib import Namespace, Graph, RDF, URIRef, Literal
from flask import Flask, request, render_template
import SPARQLWrapper
from rdflib.namespace import FOAF

import AgentUtil
from AgentUtil.ACLMessages import build_message, send_message
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Agent import Agent
from AgentUtil.Logging import config_logger
import AgentUtil.Agents

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


@app.route("/add_items", methods=['GET', 'POST'])
def browser_search():
    global dsgraph
    if request.method == 'GET':
        return render_template('addProduct.html')
    else:

        query = """
        
          prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
          INSERT
          {
              ?Producto ab:n_ref ?n_ref.
              ?Producto ab:nombre ?nombre.
              ?Producto ab:descripcion ?descripcion.
              ?Producto ab:modelo ?modelo.
              ?Producto ab:precio ?precio.
              ?Producto ab:peso ?peso.
              ?Producto ab:precio ?precio.
            """

        if request.form["cantidad"] != "":
            for x in range(0, int(request.form["cantidad"])):
                query += "?Producto ab:id ?" + str(x)
                sparql.setQuery(query)
                sparql.query()

    return render_template("search.html")


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
    app.run(host=AgentUtil.Agents.hostname, port=AgentUtil.Agents.REPRESENTANTE_PORT)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')
