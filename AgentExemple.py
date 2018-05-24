# -*- coding: utf-8 -*-
"""
Ejemplo de agente para implementar los vuestros.

@author: Swaggaaa
"""

from __future__ import print_function
from multiprocessing import Process, Queue
import socket

from rdflib import Namespace, Graph, RDF
from flask import Flask

from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Agent import Agent
from AgentUtil.Logging import config_logger

# Para el sleep
import time

__author__ = 'Swaggaaa'

# Configuration stuff
hostname = socket.gethostname()
port = 9010

agn = Namespace("http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#")

# Contador de mensajes
mss_cnt = 0

# Datos del Agente

# Agent(name, uri, address, stop)
AgenteEjemplo = Agent('AgenteEjemplo',
                      agn.AgenteEjemplo,
                      'http://%s:%d/comm' % (hostname, port),
                      'http://%s:%d/Stop' % (hostname, port))

# Global triplestore graph
dsgraph = Graph()

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
        # https://www.youtube.com/watch?v=FvGndkpa4K0
        # Este video ma salvao la vida
        res = graph.query("""
                        prefix ab:<http://www.semanticweb.org/elenaalonso/ontologies/2018/4/OnlineShop#>
                        
                        SELECT ?nombre ?direccion
                        WHERE
                        {  
                            ?Centro_logistico rdf:type ab:Centro_logistico.
                            ?Centro_logistico ab:nombre ?nombre.
                            ?Centro_logistico ab:direccion ?direccion.
                        }""", initNs={'ab': agn})
        for row in res:
            print("nombre: %s   |   direccion: %s " % row)

        time.sleep(1)
        pass

    pass


if __name__ == '__main__':
    # Inicializo el grafo de ejemplo
    dsgraph.parse("ejemplo.rdf")
    cola1.put(dsgraph)

    # Debug
    print(dsgraph.serialize(format='turtle'))

    # Ponemos en marcha los behaviors y pasamos la cola para transmitir información
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')
