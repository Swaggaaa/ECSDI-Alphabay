# -*- coding: utf-8 -*-
"""
Ejemplo de agente para implementar los vuestros.

@author: Swaggaaa
"""

from __future__ import print_function

import logging
import random
from datetime import datetime
from multiprocessing import Queue

from flask import Flask, request, render_template, make_response, session
from rdflib import Graph

import AgentUtil.Agents
import AgentUtil.SPARQLHelper
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Logging import config_logger
from AgentUtil.SPARQLHelper import filterSPARQLValues
from models.InfoProducto import InfoProducto
from models.Producto import Producto

# Para el sleep

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
                                             host_vendedor=AgentUtil.Agents.VENDEDOR_HOSTNAME + ':' + str(
                                                 AgentUtil.Agents.VENDEDOR_PORT),
                                             username=request.form['nombre'],
                                             host_representante=AgentUtil.Agents.REPRESENTANTE_HOSTNAME + ':' + str(
                                                 AgentUtil.Agents.REPRESENTANTE_PORT),
                                             host_evaluador=AgentUtil.Agents.EVALUADOR_HOSTNAME + ':' + str(
                                                 AgentUtil.Agents.EVALUADOR_PORT)

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

        all_empty = True
        if request.form["n_ref"] != "":
            all_empty = False
            query += "FILTER regex(str(?n_ref), '^%s$')." % request.form["n_ref"]
        if request.form["nombre"] != "":
            all_empty = False
            query += "FILTER regex(str(?nombre), '%s')." % request.form["nombre"]
        if request.form["modelo"] != "":
            all_empty = False
            query += "FILTER regex(str(?modelo), '%s')." % request.form["modelo"]
        if request.form["calidad"] != "Any":
            all_empty = False
            query += "FILTER regex(str(?calidad), '^%s$')." % request.form["calidad"]
        if request.form["minprecio"] != "":
            all_empty = False
            query += "FILTER (?precio >= %s)." % request.form["minprecio"]
        if request.form["maxprecio"] != "":
            all_empty = False
            query += "FILTER (?precio <= %s)." % request.form["maxprecio"]

        query += "FILTER regex(str(?estado), '^%s$')." % 'Disponible'

        query += "} GROUP BY ?n_ref"

        results = AgentUtil.SPARQLHelper.read_query(query)

        try:
            results["results"]["bindings"][0]["n_ref"]
        except KeyError:
            del results["results"]["bindings"][0]

        recomendaciones = []
        recomendacion = None
        if not all_empty:
            query = """
                           prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
    
                          INSERT DATA{ 
                              ab:Busqueda%(id)s rdf:type ab:Busqueda .
                              ab:Busqueda%(id)s ab:realizada_por '%(usuario)s' .
                              ab:Busqueda%(id)s ab:n_ref '%(n_ref)s' .
                              ab:Busqueda%(id)s ab:nombre '%(nombre)s' .
                              ab:Busqueda%(id)s ab:modelo '%(modelo)s' .
                              ab:Busqueda%(id)s ab:calidad '%(calidad)s' .
                              ab:Busqueda%(id)s ab:precio_min '%(precio_min)s' .
                              ab:Busqueda%(id)s ab:precio_max '%(precio_max)s' . }                          
                          """ % {'id': random.randint(0, 999999999), 'usuario': session['username'],
                                 'n_ref': request.form['n_ref'], 'nombre': request.form['nombre'],
                                 'calidad': request.form['calidad'], 'modelo': request.form['modelo'],
                                 'precio_min': request.form['minprecio'], 'precio_max': request.form['maxprecio']}

            AgentUtil.SPARQLHelper.update_query(query)

        # Buscamos coincidencias con nombre
        query = """
                    prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
                    
                    SELECT DISTINCT ?nombre
                    WHERE {
                            ?Busqueda rdf:type ab:Busqueda .
                            ?Busqueda ab:nombre ?nombre .
                            ?Busqueda ab:realizada_por ?realizada_por .
                            FILTER regex(str(?realizada_por), '%s') .
                        }
                    
                    """ % session['username']

        nombres_buscados = AgentUtil.SPARQLHelper.read_query(query)['results']['bindings']
        nombres = []
        for n in nombres_buscados:
            nombres.append(n['nombre']['value'])

        query = """
        prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
                    
                    SELECT DISTINCT ?n_ref
                    WHERE {
                            ?Producto rdf:type ab:Producto .
                            ?Producto ab:nombre ?nombre .
                            ?Producto ab:n_ref ?n_ref .
        
            """

        entered = False
        for nombre in nombres:
            if nombre == '':
                continue
            entered = True
            query += "FILTER regex(str(?nombre), '%s') . " % nombre

        if not entered:
            query += "FILTER regex(str(?nombre), 'zzzzzzzz') . "

        query += " } "

        res = AgentUtil.SPARQLHelper.read_query(query)
        for product in res['results']['bindings']:
            if product['n_ref']['value'] != '':
                recomendaciones.append(product['n_ref']['value'])

        # Buscamos coincidencias con modelo
        query = """
                            prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
                            SELECT DISTINCT ?modelo
                            WHERE {
                                    ?Busqueda rdf:type ab:Busqueda .
                                    ?Busqueda ab:modelo ?modelo .
                                    ?Busqueda ab:realizada_por ?realizada_por .
                                    FILTER regex(str(?realizada_por), '%s') .
                        }
                    
                    """ % session['username']

        modelos_buscados = AgentUtil.SPARQLHelper.read_query(query)
        modelos_buscados = modelos_buscados['results']['bindings']
        modelos = []
        for m in modelos_buscados:
            modelos.append(m['modelo']['value'])

        query = """
                prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
                
                            SELECT DISTINCT ?n_ref
                            WHERE {
                                    ?Producto rdf:type ab:Producto .
                                    ?Producto ab:modelo ?modelo .
                                    ?Producto ab:n_ref ?n_ref .
                    """

        entered = False
        for modelo in modelos:
            if modelo == '':
                continue
            entered = True
            query += "FILTER regex(str(?modelo), '%s') . " % modelo

        if not entered:
            query += "FILTER regex(str(?modelo), 'zzzzzzzz') . "

        query += " } "

        res = AgentUtil.SPARQLHelper.read_query(query)
        for product in res['results']['bindings']:
            if product['n_ref']['value'] != '':
                recomendaciones.append(product['n_ref']['value'])

        query = """
                prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
                
                SELECT ?n_ref (SAMPLE(?id) AS ?n_ref_id) (SAMPLE(?nombre) AS ?n_ref_nombre) (SAMPLE(?modelo) AS 
            ?n_ref_modelo) (SAMPLE(?calidad) AS ?n_ref_calidad) (SAMPLE(?precio) AS ?n_ref_precio)
            (COUNT(*) AS ?disponibilidad)
            
            WHERE 
            { 
                %s
                ?Producto ab:id ?id.
                ?Producto ab:n_ref ?n_ref.
                ?Producto ab:nombre ?nombre.
                ?Producto ab:modelo ?modelo.
                ?Producto ab:calidad ?calidad.
                ?Producto ab:precio ?precio. 
                }GROUP BY ?n_ref
            
            """ % AgentUtil.SPARQLHelper.filterSPARQLValues("?n_ref", recomendaciones, False)

        recomendacion = AgentUtil.SPARQLHelper.read_query(query)

        # Recomendaciones segun valoraciones

        query = """
                    prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
                    
                    SELECT ?sobre_un 
                    WHERE {
                            ?Valoracion ab:sobre_un ?sobre_un .
                            ?Valoracion ab:autor '%s'
                            }
                        """ % session['username']

        productos_valorados = AgentUtil.SPARQLHelper.read_query(query)
        valorados = []
        for p in productos_valorados['results']['bindings']:
            valorados.append(p['sobre_un']['value'])

        query = """
                    prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
                    
                    SELECT DISTINCT ?marca
                    WHERE {
                        %s
                        ?Producto rdf:type ab:Producto .
                        ?Producto ab:marca ?marca .
                        ?Producto ab:n_ref ?n_ref }
        """ % AgentUtil.SPARQLHelper.filterSPARQLValues("?n_ref", valorados, False)

        marcas_valoradas = AgentUtil.SPARQLHelper.read_query(query)

        marcas_positivas = []
        for marca in marcas_valoradas['results']['bindings']:
            query = """
                            prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
                            SELECT DISTINCT ?n_ref
                            WHERE {
                                ?Producto rdf:type ab:Producto .
                                ?Producto ab:n_ref ?n_ref .
                                ?Producto ab:marca "%s" }
                            """ % marca['marca']['value']

            productos_marca = AgentUtil.SPARQLHelper.read_query(query)
            productos = []

            for p in productos_marca['results']['bindings']:
                productos.append(p['n_ref']['value'])
            query = """
                            prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
                            
                            SELECT ?puntuacion
                            WHERE {
                                %(filter)s
                                ?Valoracion ab:sobre_un ?sobre_un .
                                ?Valoracion ab:autor '%(autor)s' .
                                ?Valoracion ab:puntuacion ?puntuacion }
                            """ % {'filter': AgentUtil.SPARQLHelper.filterSPARQLValues("?sobre_un", productos, True),
                                   'autor': session['username']}
            puntuacion = AgentUtil.SPARQLHelper.read_query(query)
            puntuacion = puntuacion['results']['bindings']

            count = 0
            score = 0

            for p in puntuacion:
                count += 1
                score += int(p['puntuacion']['value'])

            if (count != 0):
                puntuacion = score / count
                if (puntuacion > 3):
                    marcas_positivas.append(marca['marca']['value'])

        query = """
                            prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
                            
                            SELECT ?n_ref (SAMPLE(?id) AS ?n_ref_id) (SAMPLE(?nombre) AS ?n_ref_nombre) (SAMPLE(?modelo) AS 
                                    ?n_ref_modelo) (SAMPLE(?calidad) AS ?n_ref_calidad) (SAMPLE(?precio) AS ?n_ref_precio)
                                    (COUNT(*) AS ?disponibilidad)
                            WHERE {
                                %s
                                ?Producto ab:id ?id.
                                ?Producto ab:n_ref ?n_ref.
                                ?Producto ab:nombre ?nombre.
                                ?Producto ab:modelo ?modelo.
                                ?Producto ab:calidad ?calidad.
                                ?Producto ab:precio ?precio.
                                ?Producto ab:marca ?marca .
                                }GROUP BY ?n_ref
                            """ % AgentUtil.SPARQLHelper.filterSPARQLValues("?marca", marcas_positivas, True)

        rec = AgentUtil.SPARQLHelper.read_query(query)

        try:
            if recomendacion is not None:
                recomendacion["results"]["bindings"][0]["n_ref"]
        except KeyError:
            del recomendacion["results"]["bindings"][0]

        try:
            rec["results"]["bindings"][0]["n_ref"]
        except KeyError:
            del rec["results"]["bindings"][0]

        return render_template("results.html", products=results, username=session['username'],
                               recomendaciones=recomendacion, segun_valoraciones=rec, host_vendedor=(
                    AgentUtil.Agents.VENDEDOR_HOSTNAME + ':' + str(AgentUtil.Agents.VENDEDOR_PORT)))


@app.route("/rate", methods=['GET', 'POST'])
def browser_rate():
    global dsgraph
    if request.method == 'GET':
        session['username'] = request.args.get('user')

        no_valorados = get_productos_a_valorar()

        return render_template("ratings.html", products=no_valorados, host_evaluador=(
                AgentUtil.Agents.EVALUADOR_HOSTNAME + ':' + str(AgentUtil.Agents.EVALUADOR_PORT)),
                               username=session['username'])

    else:

        query = """prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
                    INSERT DATA{
                        ab:Valoracion%(autor)s%(sobre)s ab:autor '%(autor)s' .
                        ab:Valoracion%(autor)s%(sobre)s ab:puntuacion '%(puntuacion)s' .
                        ab:Valoracion%(autor)s%(sobre)s ab:comentario '%(comentario)s' .
                        ab:Valoracion%(autor)s%(sobre)s ab:sobre_un '%(sobre)s' . }
                """ % {'autor': session['username'], 'puntuacion': request.form['punctuation'],
                       'comentario': request.form['opinion'], 'sobre': request.form['product']}

        AgentUtil.SPARQLHelper.update_query(query)

        no_valorados = get_productos_a_valorar()

        return render_template("ratings.html", products=no_valorados, host_evaluador=(
                AgentUtil.Agents.EVALUADOR_HOSTNAME + ':' + str(AgentUtil.Agents.EVALUADOR_PORT)),
                               username=session['username'])


def get_productos_a_valorar():
    fecha_actual = datetime.now()

    query = """
                                     prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
    
                                    SELECT ?id ?compuesto_por ?fecha_entrega
                                    WHERE {
                                        ?Pedido ab:id ?id .
                                        ?Pedido ab:compuesto_por ?compuesto_por.
                                        ?Pedido ab:fecha_entrega ?fecha_entrega .
                                        ?Pedido ab:comprado_por ?comprado_por .
                                """
    query += "FILTER regex (str(?comprado_por), '%s')." % session['username']
    # query += "FILTER (?fecha_entrega < '%s')"%fecha_actual
    query += '}'

    res = AgentUtil.SPARQLHelper.read_query(query)
    pedidos = res['results']['bindings']
    no_valorados = []
    ids = []
    for pedido in pedidos:
        # fecha_entrega = pedido['fecha_entrega']['value']
        # fecha_entrega = datetime.strptime(fecha_entrega, "%Y-%m-%d %H:%M:%S.%f")
        # diff = (fecha_actual - fecha_entrega).total_seconds()
        diff = 150
        if diff > 120:
            ids.append(pedido["compuesto_por"]["value"])

    query = """
                                           prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
    
                                           SELECT DISTINCT ?nombre ?n_ref
                                           WHERE {
                                               %s
                                               ?Producto ab:id ?id .
                                               ?Producto ab:nombre ?nombre .
                                               ?Producto ab:n_ref ?n_ref .
                                                }
                                       """ % AgentUtil.SPARQLHelper.filterSPARQLValues("?id", ids, False)

    res = AgentUtil.SPARQLHelper.read_query(query)

    nrefs = res['results']['bindings']
    sin_valoracion = []
    for ref in nrefs:
        query = """
                                    prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
    
                                    SELECT *
                                    WHERE {?Valoracion ab:sobre_un '%(n_ref)s' .
                                          ?Valoracion ab:autor '%(username)s' .
                                          }""" % {'n_ref': ref['n_ref']['value'], 'username': session['username']}
        res = AgentUtil.SPARQLHelper.read_query(query)
        if len(res['results']['bindings']) == 0:
            sin_valoracion.append(ref)

    for p in sin_valoracion:
        producto = Producto()
        producto.id = pedido['compuesto_por']['value']
        producto.n_ref = p['n_ref']['value']
        producto.nombre = p['nombre']['value']

        no_valorados.append(producto)

    return no_valorados


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
    app.run(host=AgentUtil.Agents.EVALUADOR_HOSTNAME, port=AgentUtil.Agents.EVALUADOR_PORT, threaded=True)

    print('The End')
