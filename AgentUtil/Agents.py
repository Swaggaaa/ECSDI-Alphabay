import socket

from rdflib import Namespace

from AgentUtil.Agent import Agent
from AgentUtil.OntoNamespaces import AB

EVALUADOR_PORT = 9020
VENDEDOR_PORT = 9030
CENTROLOG_PORT = 9040
TRANSPORTISTA_PORT = 9050
TRANSPORTISTA2_PORT = 9051
REPRESENTANTE_PORT = 9060

NUM_TRANSPORTISTAS = 2

hostname = socket.gethostname()
endpoint_read = 'http://localhost:5820/myDB/query'
endpoint_update = 'http://localhost:5820/myDB/update'

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

AgenteTransportista = Agent('SEUR',
                            AB.AgenteTransportista,
                            'http://%s:%d/comm' % (hostname, TRANSPORTISTA_PORT),
                            'http://%s:%d/Stop' % (hostname, TRANSPORTISTA_PORT))

AgenteTransportista2 = Agent('CORREOS',
                             AB.AgenteTransportista2,
                             'http://%s:%d/comm' % (hostname, TRANSPORTISTA2_PORT),
                             'http://%s:%d/Stop' % (hostname, TRANSPORTISTA2_PORT))

AgenteRepresentante = Agent('AgenteRepresentante',
                              AB.AgenteRepresentante,
                              'http://%s:%d/comm' % (hostname, REPRESENTANTE_PORT),
                              'http://%s:%d/Stop' % (hostname, REPRESENTANTE_PORT))