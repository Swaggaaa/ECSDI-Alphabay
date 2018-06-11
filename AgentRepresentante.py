# -*- coding: utf-8 -*-

from __future__ import print_function

import logging
from multiprocessing import Queue

from flask import Flask, request, render_template
from rdflib import Graph

import AgentUtil
import AgentUtil.Agents
import AgentUtil.SPARQLHelper
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Logging import config_logger

# Para el sleep

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
                                            ab:Producto%(productoid)s ab:estado 'Disponible' .
                                        }
                                            """ % {'productoid': id_product,
                                                   'id': id_product, 'modelo': '"' + request.form["modelo"] + '"',
                                                   'nombre': '"' + request.form["nombre"] + '"',
                                                   'precio': float(request.form["precio"]),
                                                   'descripcion': '"' + request.form["descripcion"] + '"',
                                                   'marca': '"' + request.form["marca"] + '"',
                                                   'n_ref': int(request.form["n_ref"]),
                                                   'peso': float(request.form["peso"]),
                                                   'vendido_por': '"' + request.form["vendido_por"] + '"',
                                                   'calidad': '"' + request.form["calidad"] + '"'}

                res = AgentUtil.SPARQLHelper.update_query(query)

                logger.info("[#] Hemos añadido un nuevo producto al catalogo con id: %s" % id_product)

        return render_template("add_product_ok.html", host_evaluador=(
                AgentUtil.Agents.EVALUADOR_HOSTNAME + ':' + str(AgentUtil.Agents.EVALUADOR_PORT)))


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


if __name__ == '__main__':
    # Ponemos en marcha el servidor
    app.run(host=AgentUtil.Agents.REPRESENTANTE_HOSTNAME, port=AgentUtil.Agents.REPRESENTANTE_PORT, threaded=True)

    print('The End')
