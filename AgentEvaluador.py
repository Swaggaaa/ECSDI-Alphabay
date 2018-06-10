# -*- coding: utf-8 -*-
"""
Ejemplo de agente para implementar los vuestros.

@author: Swaggaaa
"""

from __future__ import print_function

import logging
from multiprocessing import Process, Queue
import socket

from rdflib import Namespace, Graph, RDF, URIRef
from flask import Flask, request, render_template, make_response, session
import SPARQLWrapper

from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Agent import Agent
from AgentUtil.Logging import config_logger
import AgentUtil.Agents
import AgentUtil.SPARQLHelper

# Para el sleep
import time

from models.InfoProducto import InfoProducto
from models.Pedido import Pedido
from models.Producto import Producto

__author__ = 'Swaggaaa'

# Contador de mensajes
mss_cnt = 0

# Datos del Agente

# Global triplestore graph
dsgraph = Graph()

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
logger = config_logger(level=1)

cola1 = Queue()

# Flask stuff
app = Flask(__name__)
app.secret_key = 'AgentEvaluador'


# Esto en verdad no es de este agente, pero lo ponemos aqui para poder tener el indice de paginas en algun lado
@app.route("/", methods=['GET', 'POST'])
def login():
    global dsgraph
    if request.method == 'GET':
        return render_template("login.html")
    else:
        resp = make_response(render_template("index.html",
                                             host_vendedor=AgentUtil.Agents.hostname + ':' + str(
                                                 AgentUtil.Agents.VENDEDOR_PORT),
                                             username=request.form['nombre'],
                                             host_representante=AgentUtil.Agents.hostname + ':' + str(
                                                 AgentUtil.Agents.REPRESENTANTE_PORT)
                                             ))
        session['username'] = request.form['nombre']
        return resp


class Info_Pedido(object):
    pass


@app.route("/info", methods={'GET'})
def info():
    global dsgraph
    if request.method == 'GET':
        query = """
               prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
                       
               SELECT ?id ?fecha_entrega ?compuesto_por ?es_transportado_por
               WHERE {
                    ?Pedido rdf:type ab:Pedido .
                    ?Pedido ab:id ?id .    
                    ?Pedido ab:fecha_entrega ?fecha_entrega .    
                    ?Pedido ab:compuesto_por ?compuesto_por .    
                    ?Pedido ab:es_transportado_por ?es_transportado_por .    
                    ?Pedido ab:comprado_por '%s' . }   
        """ % session['username']

        res = AgentUtil.SPARQLHelper.read_query(query)

        lista_productos = {}
        for pedido in res["results"]["bindings"]:
            info_producto = InfoProducto()
            info_producto.id = pedido["compuesto_por"]["value"]
            info_producto.transportista = pedido["es_transportado_por"]["value"]
            info_producto.fecha = pedido["fecha_entrega"]["value"]
            lista_productos[pedido["compuesto_por"]["value"]] = info_producto

        lista_ids = [producto for producto in lista_productos]
        query = """
        prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
              
        SELECT ?id ?nombre
        WHERE {
            %s
            ?Producto rdf:type ab:Producto .
            ?Producto ab:id ?id .
            ?Producto ab:nombre ?nombre . }
        """ % AgentUtil.SPARQLHelper.filterSPARQLValues("?id", lista_ids, False)

        res = AgentUtil.SPARQLHelper.read_query(query)

        for producto in res["results"]["bindings"]:
            lista_productos[producto["id"]["value"]].nombre = producto["nombre"]["value"]

        return render_template('info.html', productos=lista_productos)


@app.route("/search", methods=['GET', 'POST'])
def browser_search():
    global dsgraph
    if request.method == 'GET':
        return render_template("search.html")
    else:
        query = """
               prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>

              SELECT ?n_ref (SAMPLE(?id) AS ?n_ref_id) (SAMPLE(?nombre) AS ?n_ref_nombre) (SAMPLE(?modelo) AS 
              ?n_ref_modelo) (SAMPLE(?calidad) AS ?n_ref_calidad) (SAMPLE(?precio) AS ?n_ref_precio)
              (COUNT(*) AS ?disponibilidad)
              
              WHERE 
              {
                  ?Producto ab:id ?id.
                  ?Producto ab:n_ref ?n_ref.
                  ?Producto ab:nombre ?nombre.
                  ?Producto ab:modelo ?modelo.
                  ?Producto ab:calidad ?calidad.
                  ?Producto ab:precio ?precio.
                  ?Producto ab:estado ?estado.
              """
        if request.form["n_ref"] != "":
            query += "FILTER regex(str(?n_ref), '^%s$')." % request.form["n_ref"]
        if request.form["nombre"] != "":
            query += "FILTER regex(str(?nombre), '%s')." % request.form["nombre"]
        if request.form["modelo"] != "":
            query += "FILTER regex(str(?modelo), '%s')." % request.form["modelo"]
        if request.form["calidad"] != "Any":
            query += "FILTER regex(str(?calidad), '^%s$')." % request.form["calidad"]
        if request.form["minprecio"] != "":
            query += "FILTER (?precio >= %s)." % request.form["minprecio"]
        if request.form["maxprecio"] != "":
            query += "FILTER (?precio <= %s)." % request.form["maxprecio"]

        query += "FILTER regex(str(?estado), '^%s$')." % 'Disponible'

        query += "} GROUP BY ?n_ref"

        res = AgentUtil.SPARQLHelper.read_query(query)

        try:
            res["results"]["bindings"][0]["n_ref"]
        except KeyError:
            del res["results"]["bindings"][0]

        return render_template("results.html", products=res, host_vendedor=(
                AgentUtil.Agents.hostname + ':' + str(AgentUtil.Agents.VENDEDOR_PORT)),
                               username=session['username'])


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
    app.run(host=AgentUtil.Agents.hostname, port=AgentUtil.Agents.EVALUADOR_PORT)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')
