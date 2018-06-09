# -*- coding: utf-8 -*-
"""
Ejemplo de agente para implementar los vuestros.

@author: Swaggaaa
"""

from __future__ import print_function
from multiprocessing import Process, Queue
import socket

from rdflib import Namespace, Graph, RDF, URIRef
from AgentUtil.ACLMessages import build_message, send_message, get_message_properties
from AgentUtil.OntoNamespaces import ACL, AB
from flask import Flask, request, render_template, make_response
import SPARQLWrapper

from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Agent import Agent
from AgentUtil.Logging import config_logger
import AgentUtil.Agents
import AgentUtil.SPARQLHelper

# Para el sleep
import time

__author__ = 'Swaggaaa'

# Contador de mensajes
mss_cnt = 0

# Datos del Agente

# Global triplestore graph
dsgraph = Graph()

logger = config_logger(level=1)

cola1 = Queue()

# Flask stuff
app = Flask(__name__)


# Esto en verdad no es de este agente, pero lo ponemos aqui para poder tener el indice de paginas en algun lado
@app.route("/login", methods=['GET', 'POST'])
def login():
    global dsgraph
    if request.method == 'GET':
        return render_template("login.html")
    else:
        resp = make_response(render_template("index.html"))
        resp.set_cookie('username', request.form['user'])
        return resp


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

        query += "} GROUP BY ?n_ref"

        res = AgentUtil.SPARQLHelper.read_query(query)

        try:
            res["results"]["bindings"][0]["n_ref"]
        except KeyError:
            del res["results"]["bindings"][0]

        return render_template("results.html", products=res, host_vendedor=(
                AgentUtil.Agents.hostname + ':' + str(AgentUtil.Agents.VENDEDOR_PORT)))


# Aqui se recibiran todos los mensajes. A diferencia de una API Rest (como hacemos en ASW o PES), aqui hay solo 1
# única ruta, y luego filtramos por el contenido de los mensajes y las órdenes que contengan
@app.route("/comm")
def comunicacion():
    global dsgraph
    global mss_cnt

    logger.info('Peticion de informacion recibida')

    message = request.args['content']
    gm = Graph()
    gm.parse(data=message)
    gr = None

    msgdic = get_message_properties(gm)
    if msgdic is None:
        gr = build_message(Graph(), ACL['not-understood'], sender=AgentUtil.Agents.AgenteEvaluador.uri,
                           msgcnt=mss_cnt)
    else:
        perf = msgdic['performative']

        # Se nos solicita que obtengamos los productos parecidos a partir de la info
        if perf == ACL.request:
            if 'content' in msgdic:
                content = msgdic['content']

                if 'prueba' in str(content):
                    prioridad = gm.value(subject=content, predicate=AB.prioridad)
                    print("PRIORIDAD " + prioridad)

            else:
                gr = build_message(Graph(), ACL['not-understood'], sender=AgentUtil.Agents.AgenteEvaluador.uri,
                                   msgcnt=mss_cnt)
    mss_cnt += 1
    logger.info('Respondemos a la peticion')

    return gr.serialize(format='xml')


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


def recomendation_behavior():
    global mss_cnt
    while True:
        logger.info('Nos registramos')
        print("SE ENVIA AQUI " + AgentUtil.Agents.AgenteEvaluador.address)
        # Cada 3 minutos (mock) enviamos un mensaje al agente de "Enviar lotes preparados"
        gr = Graph()
        gr.bind('ab', AB)
        content = AB[AgentUtil.Agents.AgenteEvaluador.name + '-prueba']
        gr.add((content, AB.prioridad, 'express'))
        msg = build_message(gr, perf=ACL.request,
                            sender=AgentUtil.Agents.AgenteEvaluador.uri,
                            receiver=AgentUtil.Agents.AgenteEvaluador.uri,
                            content=content,
                            msgcnt=mss_cnt)
        send_message(msg, AgentUtil.Agents.AgenteEvaluador.address)
        mss_cnt += 1
        #   time.sleep(100)
        pass
    pass


if __name__ == '__main__':
    # Ponemos en marcha los behaviors y pasamos la cola para transmitir información
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()
    ab2 = Process(target=recomendation_behavior)
    ab2.start()

    # Ponemos en marcha el servidor
    app.run(host=AgentUtil.Agents.hostname, port=AgentUtil.Agents.EVALUADOR_PORT)

    # Esperamos a que acaben los behaviors
    ab1.join()
    ab2.join()
    print('The End')
