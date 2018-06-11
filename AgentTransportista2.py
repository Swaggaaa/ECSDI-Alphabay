# -*- coding: utf-8 -*-
"""
Ejemplo de agente para implementar los vuestros.

@author: Swaggaaa
"""

from __future__ import print_function

import logging
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
from models.Lote import Lote
from models.Oferta import Oferta

__author__ = 'Swaggaaa'

# Contador de mensajes
mss_cnt = 0

# Global triplestore graph
dsgraph = Graph()

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
logger = config_logger(level=1)

cola1 = Queue()

# Flask stuff
app = Flask(__name__)


# Aqui se recibiran todos los mensajes. A diferencia de una API Rest (como hacemos en ASW o PES), aqui hay solo 1
# única ruta, y luego filtramos por el contenido de los mensajes y las órdenes que contengan
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

        # Se nos solicita una oferta
        if perf == ACL.request:
            if 'content' in msgdic:
                content = msgdic['content']

                if 'solicitar-oferta' in str(content):
                    lote = Lote()
                    lote.peso_total = gm.value(subject=content, predicate=AB.peso)
                    lote.ciudad_destino = gm.value(subject=content, predicate=AB.ciudad)
                    lote.prioridad = gm.value(subject=content, predicate=AB.prioridad)
                    lote.id = gm.value(subject=content, predicate=AB.id)

                    precio = float(lote.peso_total) + random.randint(-2, 2)
                    if str(lote.prioridad) == 'express':
                        precio += 6.0
                    elif str(lote.prioridad) == 'standard':
                        precio += 3.0

                    logger.info("[#] Percepcion - Solicitan oferta y ofrecemos un precio de: %s" % precio)

                    gmess = Graph()
                    gmess.bind('ab', AB)
                    content = AB[AgentUtil.Agents.AgenteTransportista2.name + '-proponer-oferta']
                    gmess.add((content, AB.id, Literal(random.randint(0, 999999999999))))
                    gmess.add((content, AB.precio, Literal(precio)))
                    gmess.add((content, AB.transportista, Literal(AgentUtil.Agents.AgenteTransportista2.name)))
                    msg = build_message(gmess, perf=ACL.propose,
                                        sender=AgentUtil.Agents.AgenteTransportista2.uri,
                                        receiver=AgentUtil.Agents.AgenteCentroLogistico.uri,
                                        content=content,
                                        msgcnt=mss_cnt)
                    send_message(msg, AgentUtil.Agents.AgenteCentroLogistico.address)
                    mss_cnt += 1

        elif perf == ACL.propose:
            if 'content' in msgdic:
                content = msgdic['content']
                if 'proponer-oferta' in str(content):

                    oferta = Oferta()
                    oferta.id = gm.value(subject=content, predicate=AB.id)
                    oferta.precio = gm.value(subject=content, predicate=AB.precio)
                    oferta.transportista = gm.value(subject=content, predicate=AB.transportista)

                    gmess = Graph()
                    gmess.bind('ab', AB)

                    decision = random.randint(0, 2)
                    if decision == 0:
                        logger.info("[#] Percepcion - Nos proponen contraoferta y la aceptamos!")
                        content = AB[AgentUtil.Agents.AgenteTransportista2.name + '-aceptar-oferta']
                        gmess.add((content, AB.id, Literal(oferta.id)))
                        gmess.add((content, AB.precio, Literal(oferta.precio)))
                        gmess.add((content, AB.transportista, Literal(oferta.transportista)))
                        msg = build_message(gmess, perf=ACL.accept_proposal,
                                            sender=AgentUtil.Agents.AgenteTransportista2.uri,
                                            receiver=AgentUtil.Agents.AgenteCentroLogistico.uri,
                                            content=content,
                                            msgcnt=mss_cnt)
                    elif decision == 1:
                        logger.info("[#] Percepcion - Nos proponen contraoferta y la rechazamos! >:(")
                        content = AB[AgentUtil.Agents.AgenteTransportista2.name + '-rechazar-oferta']
                        gmess.add((content, AB.id, Literal(oferta.id)))
                        gmess.add((content, AB.precio, Literal(oferta.precio)))
                        gmess.add((content, AB.transportista, Literal(oferta.transportista)))
                        msg = build_message(gmess, perf=ACL.reject_proposal,
                                            sender=AgentUtil.Agents.AgenteTransportista2.uri,
                                            receiver=AgentUtil.Agents.AgenteCentroLogistico.uri,
                                            content=content,
                                            msgcnt=mss_cnt)
                    else:
                        nueva_oferta = Oferta()
                        nueva_oferta.id = random.randint(0, 99999999999)
                        nueva_oferta.precio = float(oferta.precio) + float(oferta.precio) * 0.05
                        nueva_oferta.transportista = oferta.transportista

                        logger.info("[#] Percepcion - Nos proponen contraoferta y la modificamos de %s a %s euros!" %
                                    (oferta.precio, nueva_oferta.precio))

                        gmess = Graph()
                        gmess.bind('ab', AB)
                        content = AB[AgentUtil.Agents.AgenteTransportista2.name + '-informar-oferta-final']
                        gmess.add((content, AB.id, Literal(nueva_oferta.id)))
                        gmess.add((content, AB.precio, Literal(nueva_oferta.precio)))
                        gmess.add((content, AB.transportista, Literal(nueva_oferta.transportista)))
                        msg = build_message(gmess, perf=ACL.inform,
                                            sender=AgentUtil.Agents.AgenteTransportista2.uri,
                                            receiver=AgentUtil.Agents.AgenteCentroLogistico.uri,
                                            content=content,
                                            msgcnt=mss_cnt)

                    send_message(msg, AgentUtil.Agents.AgenteCentroLogistico.address)
                    mss_cnt += 1

            else:
                gr = build_message(Graph(), ACL['not-understood'], sender=AgentUtil.Agents.AgenteCentroLogistico.uri,
                                   msgcnt=mss_cnt)

        else:
            gr = build_message(Graph(), ACL['not-understood'], sender=AgentUtil.Agents.AgenteCentroLogistico.uri,
                               msgcnt=mss_cnt)

    if gr is None:
        gr = build_message(Graph(),
                           ACL['inform-done'],
                           sender=AgentUtil.Agents.AgenteCentroLogistico.uri,
                           msgcnt=mss_cnt,
                           receiver=msgdic['sender'])
        mss_cnt += 1

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


if __name__ == '__main__':
    # Ponemos en marcha los behaviors y pasamos la cola para transmitir información
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=AgentUtil.Agents.TRANSPORTISTA2_HOSTNAME, port=AgentUtil.Agents.TRANSPORTISTA2_PORT)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')
