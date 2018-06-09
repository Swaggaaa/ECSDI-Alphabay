# -*- coding: utf-8 -*-

from __future__ import print_function
from multiprocessing import Process, Queue
import socket

from rdflib import Namespace, Graph, RDF, URIRef, Literal
from flask import Flask, request, render_template
import SPARQLWrapper
from rdflib.namespace import FOAF

import AgentUtil
import AgentUtil.SPARQLHelper
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


logger = config_logger(level=1)

cola1 = Queue()

# Flask stuff
app = Flask(__name__)


@app.route("/add", methods=['GET', 'POST'])
def browser_search():
    global dsgraph
    if request.method == 'GET':
        return render_template('add_product.html')
    else:
        query = """
        
          prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
          
          SELECT (MAX(?id) as ?maxid)
          WHERE{
                ?Producto rdf:type ab:Producto .
                ?Producto ab:id ?id.
          }
                                       
            """

        res = AgentUtil.SPARQLHelper.read_query(query)

        try:
            res["results"]["bindings"][0]["maxid"]["value"]
        except KeyError:
            del res["results"]["bindings"][0]

        if request.form["cantidad"] != "":
            aux = int(res["results"]["bindings"][0]["maxid"]["value"])
            for x in range(0, int(request.form["cantidad"])):
                id_product = aux + x + 1
                query = """
                                       prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>


                                        INSERT DATA
                                        {
                                            ab:Producto%(productoid)s rdf:type ab:Producto .
                                            ab:Producto%(productoid)s ab:id %(id)d .
                                            ab:Producto%(productoid)s ab:modelo %(modelo)s .
                                            ab:Producto%(productoid)s ab:nombre %(nombre)s .
                                            ab:Producto%(productoid)s ab:precio %(precio)d .
                                            ab:Producto%(productoid)s ab:descripcion %(descripcion)s .
                                            ab:Producto%(productoid)s ab:marca %(marca)s .
                                            ab:Producto%(productoid)s ab:n_ref %(n_ref)d .
                                            ab:Producto%(productoid)s ab:peso %(peso)f .
                                            ab:Producto%(productoid)s ab:vendido_por %(vendido_por)s .
                                            ab:Producto%(productoid)s ab:calidad %(calidad)s .
                                        }
                                            """ % {'productoid': id_product,
                                                   'id': id_product, 'modelo': '"' + request.form["modelo"] + '"',
                                                   'nombre': '"' + request.form["nombre"] + '"',
                                                   'precio': int(request.form["precio"]),
                                                   'descripcion': '"' + request.form["descripcion"] + '"',
                                                   'marca': '"' + request.form["marca"] + '"',
                                                   'n_ref': int(request.form["n_ref"]),
                                                   'peso': float(request.form["peso"]),
                                                   'vendido_por': '"' + request.form["vendido_por"] + '"',
                                                   'calidad': '"' + request.form["calidad"] + '"'}

                res = AgentUtil.SPARQLHelper.update_query(query)

        return render_template("add_product_ok.html", host_evaluador=(
                    AgentUtil.Agents.hostname + ':' + str(AgentUtil.Agents.EVALUADOR_PORT)))


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
    app.run(host=AgentUtil.Agents.hostname, port=AgentUtil.Agents.REPRESENTANTE_PORT)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')
