class Pedido(object):
    def __init__(self):
        self.id = 0
        self.prioridad = ""
        self.fecha_compra = ""
        self.direccion = ""
        self.ciudad = ""
        self.compuesto_por = []
        self.peso_total = 0.0