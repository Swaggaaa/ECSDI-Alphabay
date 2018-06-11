# -*- coding: utf-8 -*-
"""
Ejemplo de agente para implementar los vuestros.

@author: Swaggaaa
"""

from __future__ import print_function

import logging
import random
# Para el sleep
import time
from multiprocessing import Process, Queue, current_process

from flask import Flask, request, render_template
from rdflib import Graph
from rdflib import Literal

import AgentUtil
import AgentUtil.Agents
import AgentUtil.SPARQLHelper
from AgentUtil.ACLMessages import build_message, send_message, get_message_properties
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Logging import config_logger
from AgentUtil.OntoNamespaces import ACL, AB
from models.Lote import Lote
from models.Oferta import Oferta
from models.Pedido import Pedido

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
app.secret_key = 'AgentCentroLogistico'

# Contador de respuestas
num_respuestas = 0

# Mejor oferta hasta ahora
best_offer = None

# Lotes en proceso de envío
lotes_enviando = []


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
            """ % AgentUtil.SPARQLHelper.filterSPARQLValues("?n_ref", request.form.getlist('items'), False)

    res = AgentUtil.SPARQLHelper.read_query(query)
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
    global best_offer
    global num_respuestas
    if current_process().name != 'MainProcess':
        return

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
        if perf == ACL.request:
            if 'content' in msgdic:
                content = msgdic['content']

                if 'enviar-lotes' in str(content):
                    prioridad = gm.value(subject=content, predicate=AB.prioridad)

                    # Enviamos los lotes del tipo que tocan
                    logger.info("[#] Percepcion - Enviar lotes de prioridad " + prioridad)
                    enviar_lotes(prioridad)

            else:
                gr = build_message(Graph(), ACL['not-understood'], sender=AgentUtil.Agents.AgenteCentroLogistico.uri,
                                   msgcnt=mss_cnt)


        elif perf == ACL.inform:
            if 'content' in msgdic:
                content = msgdic['content']

                # Contra-oferta final
                if 'informar-oferta-final' in str(content):
                    oferta = Oferta()
                    oferta.id = gm.value(subject=content, predicate=AB.id)
                    oferta.precio = gm.value(subject=content, predicate=AB.precio)
                    oferta.transportista = gm.value(subject=content, predicate=AB.transportista)

                    logger.info("[#] Percepcion - Transportista nos hace oferta final (%s) de %s euros"
                                % (oferta.id, oferta.precio))

                    nombre_transportista = 'SEUR' if msgdic['sender'] == AgentUtil.Agents.AgenteTransportista.uri \
                        else 'CORREOS'

                    if best_offer is None or best_offer.precio > oferta.precio:
                        logger.info("[#] Nueva mejor oferta | id: %s | precio: %s | transportista %s" %
                                    (oferta.id, oferta.precio, nombre_transportista))
                        best_offer = oferta
                        best_offer.transportista = nombre_transportista

                    num_respuestas += 1
                    if num_respuestas == 2:
                        aceptar_oferta(best_offer.transportista)
                        notificar_envios(best_offer.transportista)
                        best_offer = None
                        num_respuestas = 0

                else:
                    # Recibimos un pedido
                    pedido = Pedido()
                    pedido.id = gm.value(subject=content, predicate=AB.id)
                    pedido.prioridad = gm.value(subject=content, predicate=AB.prioridad)
                    pedido.fecha_compra = gm.value(subject=content, predicate=AB.direccion)
                    pedido.compuesto_por = gm.value(subject=content, predicate=AB.compuesto_por)
                    pedido.peso_total = gm.value(subject=content, predicate=AB.peso_total)
                    pedido.direccion = gm.value(subject=content, predicate=AB.direccion)
                    pedido.ciudad = gm.value(subject=content, predicate=AB.ciudad)

                    logger.info("[#] Percepcion - Organizar nuevo pedido (%s) " % pedido.id)

                    prepare_shipping(pedido)

            gr = build_message(Graph(),
                               ACL['inform-done'],
                               sender=AgentUtil.Agents.AgenteCentroLogistico.uri,
                               msgcnt=mss_cnt,
                               receiver=msgdic['sender'], )

        # Un transportista nos ha propuesto una oferta
        elif perf == ACL.propose:
            if 'content' in msgdic:
                content = msgdic['content']
                oferta = Oferta()
                oferta.id = gm.value(subject=content, predicate=AB.id)
                oferta.precio = gm.value(subject=content, predicate=AB.precio)
                oferta.transportista = gm.value(subject=content, predicate=AB.transportista)

                logger.info("[#] Percepcion - Nueva oferta (%s)" % oferta.id)
                nombre_transportista = 'SEUR' if msgdic['sender'] == AgentUtil.Agents.AgenteTransportista.uri \
                    else 'CORREOS'

                if best_offer is None or best_offer.precio > oferta.precio:
                    logger.info("[#] Nueva mejor oferta | id: %s | precio: %s | transportista %s" %
                                (oferta.id, oferta.precio, nombre_transportista))
                    best_offer = oferta
                    best_offer.transportista = nombre_transportista

                proponer_oferta(oferta)

            else:
                gr = build_message(Graph(),
                                   ACL['inform-done'],
                                   sender=AgentUtil.Agents.AgenteCentroLogistico.uri,
                                   msgcnt=mss_cnt,
                                   receiver=msgdic['sender'], )

        # Un transportista ha aceptado la contraoferta
        elif perf == ACL.accept_proposal:
            if 'content' in msgdic:
                content = msgdic['content']
                oferta = Oferta()
                oferta.id = gm.value(subject=content, predicate=AB.id)
                oferta.precio = gm.value(subject=content, predicate=AB.precio)
                oferta.transportista = gm.value(subject=content, predicate=AB.transportista)

                logger.info("[#] Percepcion - Contraoferta aceptada (%s)" % oferta.id)

                nombre_transportista = 'SEUR' if msgdic['sender'] == AgentUtil.Agents.AgenteTransportista.uri \
                    else 'CORREOS'

                if best_offer is None or best_offer.precio > oferta.precio:
                    logger.info("[#] Nueva mejor oferta | id: %s | precio: %s | transportista %s" %
                                (oferta.id, oferta.precio, nombre_transportista))
                    best_offer = oferta
                    best_offer.transportista = nombre_transportista

                num_respuestas += 1
                if num_respuestas == 2:
                    aceptar_oferta(best_offer.transportista)
                    notificar_envios(best_offer.transportista)
                    best_offer = None
                    num_respuestas = 0

            else:
                gr = build_message(Graph(),
                                   ACL['inform-done'],
                                   sender=AgentUtil.Agents.AgenteCentroLogistico.uri,
                                   msgcnt=mss_cnt,
                                   receiver=msgdic['sender'])

        # Un transportista nos ha negado la contraoferta
        elif perf == ACL.reject_proposal:
            if 'content' in msgdic:
                content = msgdic['content']
                num_respuestas += 1

                logger.info("[#] Percepcion - Contraoferta denegada :(")

                # 2 proposed agents
                if num_respuestas == 2:
                    aceptar_oferta(best_offer.transportista)
                    notificar_envios(best_offer.transportista)
                    num_respuestas = 0
                    best_offer = None

            else:
                gr = build_message(Graph(),
                                   ACL['inform-done'],
                                   sender=AgentUtil.Agents.AgenteCentroLogistico.uri,
                                   msgcnt=mss_cnt,
                                   receiver=msgdic['sender'], )

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


def enviar_lotes(prioridad):
    global lotes_enviando
    # Obtenemos los lotes con la prioridad demandada
    query = """
            prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
            
            SELECT ?id ?peso ?ciudad ?formado_por ?prioridad
            WHERE {
            ?Lote ab:id ?id .
            ?Lote ab:prioridad ?prioridad .
            ?Lote ab:peso ?peso .
            ?Lote ab:ciudad_destino ?ciudad .
            ?Lote ab:formado_por ?formado_por .
            FILTER regex(str(?prioridad), '%s')
            }     
            """ % prioridad

    res = AgentUtil.SPARQLHelper.read_query(query)

    logger.info("[#] Lotes a enviar: " + str(len(res["results"]["bindings"])))
    if len(res["results"]["bindings"]) != 0:
        # IDs a enviar
        lotes = []
        ids = []
        for lote in res["results"]["bindings"]:
            tmp = Lote()
            tmp.id = lote["id"]["value"]
            ids.append(tmp.id)
            tmp.peso_total = lote["peso"]["value"]
            tmp.ciudad_destino = lote["ciudad"]["value"]
            tmp.prioridad = lote["prioridad"]["value"]
            lotes.append(tmp)

        query = """
        prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
        
        DELETE
         { ?Lote ?p ?v }
         WHERE
         {
            %s
            ?Lote ab:id ?id .
            ?Lote ?p ?v 
         }
        """ % AgentUtil.SPARQLHelper.filterSPARQLValues("?id", ids, False)

        # Limpiamos los lotes con los nuevos a enviar
        lotes_enviando = []

        for lote in lotes:
            lotes_enviando.append(lote)
            logger.info("[#] Solicitando oferta para lote " + lote.id)
            solicita_oferta(lote)

        # Eliminamos los lotes (es decir, los enviamos)
        res = AgentUtil.SPARQLHelper.update_query(query)


def prepare_shipping(pedido):
    # Obtenemos los lotes existentes
    query = """
        prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
             
        SELECT ?id ?peso ?prioridad
        WHERE {
          ?Lote ab:id ?id .
          ?Lote ab:ciudad_destino ?ciudad_destino .
          ?Lote ab:peso ?peso .
          ?Lote ab:prioridad ?prioridad .
          FILTER (str(?ciudad_destino) = '%s' && str(?prioridad) = '%s')
          }
        """ % (pedido.ciudad, pedido.prioridad)

    res = AgentUtil.SPARQLHelper.read_query(query)

    # No existe ningún lote actualmente
    if len(res["results"]["bindings"]) == 0:
        logger.info("[#] NO existen lotes!! Creando uno para %s y %s" % (pedido.ciudad, pedido.prioridad))
        id = random.randint(1, 999999999)
        query = """
         prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
           
           INSERT DATA {
           ab:Lote%(loteid)s rdf:type ab:Lote .
           ab:Lote%(loteid)s ab:id %(id)s .
           ab:Lote%(loteid)s ab:peso %(peso)s .
           ab:Lote%(loteid)s ab:ciudad_destino '%(ciudad)s' .
           ab:Lote%(loteid)s ab:prioridad '%(prioridad)s' .
           ab:Lote%(loteid)s ab:formado_por %(pedido)s .
           }
           """ % {'loteid': id, 'id': id, 'peso': pedido.peso_total,
                  'ciudad': pedido.ciudad, 'prioridad': pedido.prioridad,
                  'pedido': pedido.id}  # TODO: Quitar el random

        res = AgentUtil.SPARQLHelper.update_query(query)

    # Ya existen lotes, vamos a coger el más vacío con mismo destino
    else:
        lote_elegido = res["results"]["bindings"][0]
        for lote in res["results"]["bindings"]:
            if float(lote_elegido["peso"]["value"]) > float(lote["peso"]["value"]):
                lote_elegido = lote

        logger.info("[#] Lote elegido: %s (peso: %s)" % (lote_elegido["id"]["value"], lote_elegido["peso"]["value"]))
        # Insertamos el pedido dentro del nuevo lote
        query = """
        prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
           
           DELETE {
                ?Lote ab:peso ?peso .
                }
           INSERT {
                ?Lote ab:peso %s .
                }
           WHERE {
                ?Lote ab:id %s .
                ?Lote rdf:type ab:Lote .
                ?Lote ab:peso ?peso .
                }
        """ % (Literal(float(lote_elegido["peso"]["value"]) + float(pedido.peso_total)),
               lote_elegido["id"]["value"])

        res = AgentUtil.SPARQLHelper.update_query(query)


def solicita_oferta(lote):
    logger.info("[#] Enviando peticion a los transportistas")
    global mss_cnt
    gmess = Graph()
    gmess.bind('ab', AB)
    content = AB[AgentUtil.Agents.AgenteCentroLogistico.name + '-solicitar-oferta']
    gmess.add((content, AB.peso, Literal(lote.peso_total)))
    gmess.add((content, AB.ciudad, Literal(lote.ciudad_destino)))
    gmess.add((content, AB.prioridad, Literal(lote.prioridad)))
    gmess.add((content, AB.id, Literal(lote.id)))
    msg = build_message(gmess, perf=ACL.request,
                        sender=AgentUtil.Agents.AgenteCentroLogistico.uri,
                        receiver=AgentUtil.Agents.AgenteTransportista.uri,
                        content=content,
                        msgcnt=mss_cnt)
    ab4 = Process(target=send_message, args=(msg, AgentUtil.Agents.AgenteTransportista.address,))
    ab4.start()
    msg2 = build_message(gmess, perf=ACL.request,
                         sender=AgentUtil.Agents.AgenteCentroLogistico.uri,
                         receiver=AgentUtil.Agents.AgenteTransportista2.uri,
                         content=content,
                         msgcnt=mss_cnt)
    ab5 = Process(target=send_message, args=(msg2, AgentUtil.Agents.AgenteTransportista2.address,))
    ab5.start()
    ab4.join()
    ab5.join()
    mss_cnt += 1


def proponer_oferta(oferta):
    global mss_cnt
    transportista = AgentUtil.Agents.AgenteTransportista if str(oferta.transportista) == 'SEUR' else \
        AgentUtil.Agents.AgenteTransportista2

    gmess = Graph()
    gmess.bind('ab', AB)

    nuevo_precio = float(oferta.precio) - (float(oferta.precio) / 10.0)
    content = AB[AgentUtil.Agents.AgenteCentroLogistico.name + '-proponer-oferta']
    gmess.add((content, AB.id, Literal(oferta.id)))
    gmess.add((content, AB.precio, Literal(nuevo_precio)))

    logger.info("[#] Proponiendo oferta a %s y bajando el precio de %s a %s" %
                (oferta.transportista, oferta.precio, nuevo_precio))

    msg = build_message(gmess, perf=ACL.propose,
                        sender=AgentUtil.Agents.AgenteCentroLogistico.uri,
                        receiver=transportista.uri,
                        content=content,
                        msgcnt=mss_cnt)

    res = send_message(msg, transportista.address)
    mss_cnt += 1


def aceptar_oferta(transportista):
    global mss_cnt
    transportista_agent = AgentUtil.Agents.AgenteTransportista if str(transportista) == 'SEUR' else \
        AgentUtil.Agents.AgenteTransportista2
    gmess = Graph()
    content = AB[AgentUtil.Agents.AgenteCentroLogistico.name + '-aceptar-oferta']

    logger.info("[#] Aceptando oferta a %s" % transportista)

    msg = build_message(gmess, perf=ACL.accept_proposal,
                        sender=AgentUtil.Agents.AgenteCentroLogistico.uri,
                        receiver=transportista_agent.uri,
                        content=content,
                        msgcnt=mss_cnt)
    res = send_message(msg, transportista_agent.address)
    mss_cnt += 1


def notificar_envios(transportista):
    global mss_cnt
    pedidos = []
    for lote in lotes_enviando:
        query = """
             prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>

             SELECT ?formado_por
             WHERE
             {
                 ?Lote ab:id ?id .
                 ?LOte ab:formado_por ?formado_por .
                 FILTER (?id = %s)
             }
             """ % lote.id

        res = AgentUtil.SPARQLHelper.read_query(query)
        for pedido in res["results"]["bindings"]:
            pedidos.append(pedido["formado_por"]["value"])

    gmess = Graph()
    content = AB[AgentUtil.Agents.AgenteCentroLogistico.name + "-notificar-envios"]
    for pedido in pedidos:
        gmess.add((content, AB.id, Literal(pedido)))
    gmess.add((content, AB.transportista, Literal(transportista)))

    logger.info("[#] Notificando al Ag. Vendedor de %s pedidos enviados" % len(pedidos))

    msg = build_message(gmess, perf=ACL.inform,
                        sender=AgentUtil.Agents.AgenteCentroLogistico.uri,
                        receiver=AgentUtil.Agents.AgenteVendedor.uri,
                        content=content,
                        msgcnt=mss_cnt)
    res = send_message(msg, AgentUtil.Agents.AgenteVendedor.address)
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
def economic_behavior():
    global mss_cnt
    while True:
        # Cada 3 minutos (mock) enviamos un mensaje al agente de "Enviar lotes preparados"
        gr = Graph()
        gr.bind('ab', AB)
        content = AB[AgentUtil.Agents.AgenteCentroLogistico.name + '-enviar-lotes']
        gr.add((content, AB.prioridad, Literal('economic')))
        msg = build_message(gr, perf=ACL.request,
                            sender=AgentUtil.Agents.AgenteCentroLogistico.uri,
                            receiver=AgentUtil.Agents.AgenteCentroLogistico.uri,
                            content=content,
                            msgcnt=mss_cnt)
        send_message(msg, AgentUtil.Agents.AgenteCentroLogistico.address)
        mss_cnt += 1
        time.sleep(330)
        pass
    pass


def standard_behavior():
    global mss_cnt
    while True:
        # Cada 3 minutos (mock) enviamos un mensaje al agente de "Enviar lotes preparados"
        gr = Graph()
        gr.bind('ab', AB)
        content = AB[AgentUtil.Agents.AgenteCentroLogistico.name + '-enviar-lotes']
        gr.add((content, AB.prioridad, Literal('standard')))
        msg = build_message(gr, perf=ACL.request,
                            sender=AgentUtil.Agents.AgenteCentroLogistico.uri,
                            receiver=AgentUtil.Agents.AgenteCentroLogistico.uri,
                            content=content,
                            msgcnt=mss_cnt)
        send_message(msg, AgentUtil.Agents.AgenteCentroLogistico.address)
        mss_cnt += 1
        time.sleep(150)
        pass
    pass


def express_behavior():
    global mss_cnt
    while True:
        # Cada 3 minutos (mock) enviamos un mensaje al agente de "Enviar lotes preparados"
        gr = Graph()
        gr.bind('ab', AB)
        content = AB[AgentUtil.Agents.AgenteCentroLogistico.name + '-enviar-lotes']
        gr.add((content, AB.prioridad, Literal('express')))
        msg = build_message(gr, perf=ACL.request,
                            sender=AgentUtil.Agents.AgenteCentroLogistico.uri,
                            receiver=AgentUtil.Agents.AgenteCentroLogistico.uri,
                            content=content,
                            msgcnt=mss_cnt)
        send_message(msg, AgentUtil.Agents.AgenteCentroLogistico.address)
        mss_cnt += 1
        time.sleep(60)
        pass
    pass


if __name__ == '__main__':
    # Nos conectamos al StarDog

    # Ponemos en marcha los behaviors y pasamos la cola para transmitir información
    ab1 = Process(target=economic_behavior)
    ab1.start()
    ab2 = Process(target=standard_behavior)
    ab2.start()
    ab3 = Process(target=express_behavior)
    ab3.start()

    # Ponemos en marcha el servidor
    app.run(host=AgentUtil.Agents.CENTROLOG_HOSTNAME, port=AgentUtil.Agents.CENTROLOG_PORT)

    # Esperamos a que acaben los behaviors
    # ab1.join()
    ab2.join()
    # ab3.join()
    print('The End')
