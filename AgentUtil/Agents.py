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

EVALUADOR_HOSTNAME = '10.10.43.205'
VENDEDOR_HOSTNAME = '10.10.43.206'
CENTROLOG_HOSTNAME = '10.10.43.205'
TRANSPORTISTA_HOSTNAME = '10.10.43.206'
TRANSPORTISTA2_HOSTNAME = '10.10.43.204'
REPRESENTANTE_HOSTNAME = '10.10.43.205'

NUM_TRANSPORTISTAS = 2

hostname = socket.gethostname()
endpoint_read = 'http://10.10.43.205:9123/myDB/query'
endpoint_update = 'http://10.10.43.205:9123/myDB/update'

AgenteEvaluador = Agent('AgenteEvaluador',
                        AB.AgentEvaluador,
                        'http://%s:%d/comm' % (EVALUADOR_HOSTNAME, EVALUADOR_PORT),
                        'http://%s:%d/Stop' % (EVALUADOR_HOSTNAME, EVALUADOR_PORT))

AgenteVendedor = Agent('AgenteVendedor',
                       AB.AgenteVendedor,
                       'http://%s:%d/comm' % (VENDEDOR_HOSTNAME, VENDEDOR_PORT),
                       'http://%s:%d/Stop' % (VENDEDOR_HOSTNAME, VENDEDOR_PORT))

AgenteCentroLogistico = Agent('AgenteCentroLogistico',
                              AB.AgenteCentroLogistico,
                              'http://%s:%d/comm' % (CENTROLOG_HOSTNAME, CENTROLOG_PORT),
                              'http://%s:%d/Stop' % (CENTROLOG_HOSTNAME, CENTROLOG_PORT))

AgenteTransportista = Agent('SEUR',
                            AB.AgenteTransportista,
                            'http://%s:%d/comm' % (TRANSPORTISTA_HOSTNAME, TRANSPORTISTA_PORT),
                            'http://%s:%d/Stop' % (TRANSPORTISTA_HOSTNAME, TRANSPORTISTA_PORT))

AgenteTransportista2 = Agent('CORREOS',
                             AB.AgenteTransportista2,
                             'http://%s:%d/comm' % (TRANSPORTISTA2_HOSTNAME, TRANSPORTISTA2_PORT),
                             'http://%s:%d/Stop' % (TRANSPORTISTA2_HOSTNAME, TRANSPORTISTA2_PORT))

AgenteRepresentante = Agent('AgenteRepresentante',
                              AB.AgenteRepresentante,
                              'http://%s:%d/comm' % (REPRESENTANTE_HOSTNAME, REPRESENTANTE_PORT),
                              'http://%s:%d/Stop' % (REPRESENTANTE_HOSTNAME, REPRESENTANTE_PORT))
