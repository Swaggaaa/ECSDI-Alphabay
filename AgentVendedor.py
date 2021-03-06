# -*- coding: utf-8 -*-
"""
@author: Swaggaaa
"""

from __future__ import print_function

import logging
import random
# Para el sleep
from datetime import datetime, timedelta
from multiprocessing import Queue

from flask import Flask, request, render_template, session
from rdflib import Graph, RDF, Literal

import AgentUtil
import AgentUtil.Agents
from AgentUtil.ACLMessages import build_message, send_message, get_message_properties
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Logging import config_logger
from AgentUtil.OntoNamespaces import ACL, AB
from AgentUtil.SPARQLHelper import filterSPARQLValues
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
app.secret_key = 'AgentVendedor'


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
                    ids = []
                    for id in gm.objects(subject=content, predicate=AB.id):
                        ids.append(id)
                    transportista = gm.value(subject=content, predicate=AB.transportista)

                    logger.info("[#] Percepcion - Debemos notificar a los usuarios de sus pedidos enviados!")
                    logger.info("[#] Han sido enviados %s pedidos" % (1 if not isinstance(ids, list) else len(ids)))
                    if isinstance(ids, list):
                        for id in ids:
                            notificar_usuario(id, transportista)
                    else:
                        notificar_usuario(ids, transportista)

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


def notificar_usuario(id, transportista):
    query = """
       prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
       
       SELECT ?fecha_compra ?prioridad ?usuario
       WHERE {
            ?Pedido ab:fecha_compra ?fecha_compra .
            ?Pedido ab:id ?id .
            ?Pedido ab:prioridad ?prioridad .
            ?Pedido ab:comprado_por ?usuario .
            FILTER (?id = %s) }
    """ % id

    res = AgentUtil.SPARQLHelper.read_query(query)

    fecha_compra = res["results"]["bindings"][0]["fecha_compra"]["value"]
    prioridad = res["results"]["bindings"][0]["prioridad"]["value"]
    usuario = res["results"]["bindings"][0]["usuario"]["value"]
    fecha_entrega = datetime.strptime(fecha_compra, "%d/%m/%Y")
    if str(prioridad) == 'express':
        fecha_entrega += timedelta(days=1)
    elif str(prioridad) == 'standard':
        fecha_entrega += timedelta(days=3)
    else:
        fecha_entrega += timedelta(days=5)

    query = """
   prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
   
   INSERT DATA {
        ab:Pedido%(id)s ab:fecha_entrega '%(fecha)s' .
        ab:Pedido%(id)s ab:es_transportado_por '%(transportista)s' .
        }
    """ % {'id': id, 'fecha': fecha_entrega, 'transportista': transportista}

    logger.info("[#] El usuario '%s' ha sido notificado del envio de su pedido" % usuario)

    res = AgentUtil.SPARQLHelper.update_query(query)


@app.route("/buy", methods=['POST'])
def browser_search():
    global dsgraph
    session['username'] = request.form['user']
    query = """
           prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>

          SELECT ?n_ref ?id ?nombre ?modelo ?calidad ?precio
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
          """ % AgentUtil.SPARQLHelper.filterSPARQLValues("?id", request.form.getlist('items'), False)

        res = AgentUtil.SPARQLHelper.read_query(query)

        pedido = Pedido()
        pedido.id = random.randint(1, 99999999)  # TODO: Get latest id
        pedido.prioridad = request.form['prioridad']
        pedido.fecha_compra = datetime.now().strftime("%d/%m/%Y")
        pedido.direccion = request.form['direccion']
        pedido.ciudad = request.form['ciudad']

        for item in request.form.getlist('items'):
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
               'ciudad': pedido.ciudad, 'peso': pedido.peso_total, 'usuario': session['username']}

        for item in pedido.compuesto_por:
            query += "ab:Pedido%(id)s ab:compuesto_por %(item)s .\n" % {'id': pedido.id, 'item': item}

        query += " }"

        res = AgentUtil.SPARQLHelper.update_query(query)

        query = """
        prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
        
        DELETE {
            ?Producto ab:estado ?estado
        }
        INSERT {
            ?Producto ab:estado 'Vendido'
        }
        WHERE {
            %s
            ?Producto ab:estado ?estado .
            ?Producto rdf:type ab:Producto .
            ?Producto ab:id ?id . }
        """ % AgentUtil.SPARQLHelper.filterSPARQLValues("?id", pedido.compuesto_por, False)

        AgentUtil.SPARQLHelper.update_query(query)  # Los marcamos como vendidos para futuras busquedas

        logger.info("[#] Creado un nuevo pedido (%s) de productos: %s" % (pedido.id, pedido.compuesto_por))

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

        gmess.add((content, AB.peso_total, Literal(peso_total)))
        msg = build_message(gmess, perf=ACL.inform,
                            sender=AgentUtil.Agents.AgenteVendedor.uri,
                            receiver=AgentUtil.Agents.AgenteCentroLogistico.uri,
                            content=content,
                            msgcnt=mss_cnt)
        send_message(msg, AgentUtil.Agents.AgenteCentroLogistico.address)
        mss_cnt += 1

        return render_template('finished.html')


@app.route("/refund", methods=['GET', 'POST'])
def browser_refund():
    global dsgraph
    if request.method == 'GET':
        session['username'] = request.args.get('user')
        query = """
                           prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>

                          SELECT ?compuesto_por
                          WHERE 
                          {
                              ?Pedido rdf:type ab:Pedido .
                              ?Pedido ab:comprado_por ?comprado_por.
                              ?Pedido ab:compuesto_por ?compuesto_por.
                          """
        query += "FILTER regex (str(?comprado_por), '%s').}" % session['username']

        res = AgentUtil.SPARQLHelper.read_query(query)
        refs = []

        for ref in res["results"]["bindings"]:
            refs.append(ref['compuesto_por']['value'])

        query = """
                           prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
        
                          SELECT DISTINCT ?id ?n_ref ?nombre ?modelo ?precio 
                          WHERE 
                          {
                                %s
                              ?Producto rdf:type ab:Producto .
                              ?Producto ab:id ?id.
                              ?Producto ab:n_ref ?n_ref.
                              ?Producto ab:nombre ?nombre.
                              ?Producto ab:modelo ?modelo.
                              ?Producto ab:precio ?precio.
                              
                          
        } """ % filterSPARQLValues("?id", refs, False)

        res = AgentUtil.SPARQLHelper.read_query(query)

        return render_template("refund.html", products=res, host_vendedor=(
                AgentUtil.Agents.VENDEDOR_HOSTNAME + ':' + str(AgentUtil.Agents.VENDEDOR_PORT)))

    else:
        if request.form["motivo"] != 'Not satisfied':
            eliminar_producto_del_pediod()
            return render_template("resolution.html",
                                   resolution="Your request has been accepted. The transport company in charge of the devolution is %s" % escoger_transportista(),
                                   host_vendedor=(
                                           AgentUtil.Agents.VENDEDOR_HOSTNAME + ':' + str(
                                       AgentUtil.Agents.VENDEDOR_PORT)
                                   ))

        else:
            fecha_actual = datetime.now()

            query = """
                prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
                
                SELECT ?fecha_entrega
                WHERE{
                    ?Pedido ab:fecha_entrega ?fecha_entrega .
                    ?Pedido ab:compuesto_por ?compuesto_por .
                    """
            query += "FILTER regex (str(?compuesto_por), '%s')." % request.form['item']
            query += "}"

            res = AgentUtil.SPARQLHelper.read_query(query)

            fecha_entrega = res["results"]["bindings"][0]["fecha_entrega"]["value"]
            fecha_entrega = datetime.strptime(fecha_entrega, "%Y-%m-%d %H:%M:%S")
            dias_pasados = fecha_actual - fecha_entrega

            if dias_pasados.days <= 15:
                eliminar_producto_del_pediod()
                return render_template("resolution.html",
                                       resolution="Your request has been accepted. The transport company in charge of the devoution is %s" % escoger_transportista(),
                                       host_vendedor=(
                                               AgentUtil.Agents.VENDEDOR_HOSTNAME + ':' + str(
                                           AgentUtil.Agents.VENDEDOR_PORT)
                                       ))
            else:
                return render_template("resolution.html",
                                       resolution="Your request has not been accepted because it has been %s days since you have received the product" % dias_pasados.days,
                                       host_vendedor=(
                                               AgentUtil.Agents.VENDEDOR_HOSTNAME + ':' + str(
                                           AgentUtil.Agents.VENDEDOR_PORT)
                                       ))


def escoger_transportista():
    query = """
            prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>

                    SELECT ?transportista
                    WHERE {?Empresa_de_transporte ab:transportista ?transportista }"""

    res = AgentUtil.SPARQLHelper.read_query(query)

    i = random.randint(1, AgentUtil.Agents.NUM_TRANSPORTISTAS)
    transportista = res["results"]["bindings"][i - 1]["transportista"]["value"]
    return transportista


def eliminar_producto_del_pediod():
    query = """
                     prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>

                           DELETE {?Pedido ab:compuesto_por %s }
    					    WHERE {?Pedido ab:compuesto_por ?compuesto_por .
                                    ?Pedido ab:id ?id}""" % request.form['item']

    AgentUtil.SPARQLHelper.update_query(query)


# Para parar el agente. Por ahora no lo necesitaremos ya que se supone que están activos 24/7 skrra
@app.route("/Stop")
def stop():
    tidyup()
    shutdown_server()
    return "Parando Servidor"


# Se hacen limpiezas en caso que tuvieramos handles, conexiones o lo que sea abierto que debe ser liberado
def tidyup():
    pass


if __name__ == '__main__':
    # Ponemos en marcha el servidor
    app.run(host=AgentUtil.Agents.VENDEDOR_HOSTNAME, port=AgentUtil.Agents.VENDEDOR_PORT, threaded=True)
    print('The End')
