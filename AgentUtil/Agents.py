import socket

from rdflib import Namespace

from AgentUtil.Agent import Agent
from AgentUtil.OntoNamespaces import AB

EVALUADOR_PORT = 9020
VENDEDOR_PORT = 9030
CENTROLOG_PORT = 9040
TRANSPORTISTA_PORT = 9050
TRANSPORTISTA2_PORT = 9051

hostname = socket.gethostname()
endpoint = 'http://localhost:5820/myDB/query'

AgenteEvaluador = Agent('AgenteEvaluador',
                        AB.AgentEvaluador,
                        'http://%s:%d/comm' % (hostname, EVALUADOR_PORT),
                        'http://%s:%d/Stop' % (hostname, EVALUADOR_PORT))

AgenteVendedor = Agent('AgenteVendedor',
                       AB.AgenteVendedor,
                       'http://%s:%d/comm' % (hostname, VENDEDOR_PORT),
                       'http://%s:%d/Stop' % (hostname, VENDEDOR_PORT))

AgenteCentroLogistico = Agent('AgenteCentroLogistico',
                              AB.AgenteCentroLogistico,
                              'http://%s:%d/comm' % (hostname, CENTROLOG_PORT),
                              'http://%s:%d/Stop' % (hostname, CENTROLOG_PORT))

AgenteTransportista = Agent('AgenteTransportista',
                            AB.AgenteTransportista,
                            'http://%s:%d/comm' % (hostname, TRANSPORTISTA_PORT),
                            'http://%s:%d/Stop' % (hostname, TRANSPORTISTA_PORT))

AgenteTransportista2 = Agent('AgenteTransportista',
                             AB.AgenteTransportista2,
                             'http://%s:%d/comm' % (hostname, TRANSPORTISTA2_PORT),
                             'http://%s:%d/Stop' % (hostname, TRANSPORTISTA2_PORT))
