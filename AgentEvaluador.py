# -*- coding: utf-8 -*-
"""
Ejemplo de agente para implementar los vuestros.

@author: Swaggaaa
"""

from __future__ import print_function
from multiprocessing import Process, Queue
import socket

from rdflib import Namespace, Graph, RDF, URIRef
from rdflib.namespace import RDF, SKOS
from rdflib.plugins.stores import sparqlstore
from flask import Flask, request, render_template
from SPARQLWrapper import SPARQLWrapper, JSON

from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Agent import Agent
from AgentUtil.Logging import config_logger

# Para el sleep
import time

__author__ = 'Swaggaaa'

# Configuration stuff
hostname = socket.gethostname()
port = 9020

agn = Namespace("http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#")

# Contador de mensajes
mss_cnt = 0

# Datos del Agente

# Agent(name, uri, address, stop)
AgenteEvaluador = Agent('AgenteEvaluador',
                        agn.AgenteEvaluador,
                        'http://%s:%d/comm' % (hostname, port),
                        'http://%s:%d/Stop' % (hostname, port))

# Global triplestore graph
dsgraph = Graph()

endpoint = 'http://localhost:5820/myDB/query'
sparql = SPARQLWrapper(endpoint)


logger = config_logger(level=1)

cola1 = Queue()

# Flask stuff
app = Flask(__name__)


@app.route("/search", methods=['GET', 'POST'])
def browser_search():
    global dsgraph
    if request.method == 'GET':
        return render_template("search.html")
    else:
        search_content = request.form["search"]
        sparql.setQuery("""
                               prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>

                              SELECT ?n_ref ?nombre ?modelo
                              WHERE 
                              {
                                  ?Producto rdf:type ab:Producto.
                                  ?Producto ab:n_ref ?n_ref.
                                  ?Producto ab:nombre ?nombre.
                                  ?Producto ab:modelo ?modelo.
                                  FILTER regex(str(?n_ref), "^%s$").
                              }""" % search_content)
        res = sparql.query().convert()

        return render_template("results.html", products=res)


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
    sparql.setReturnFormat(JSON)

    # Ponemos en marcha los behaviors y pasamos la cola para transmitir información
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')
