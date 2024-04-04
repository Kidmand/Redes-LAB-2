#!/usr/bin/env python
# encoding: utf-8
# Revisión 2019 (a Python 3 y base64): Pablo Ventura
# Revisión 2014 Carlos Bederián
# Revisión 2011 Nicolás Wolovick
# Copyright 2008-2010 Natalia Bidart y Daniel Moisset
# $Id: server.py 656 2013-03-18 23:49:11Z bc $

import sys
import optparse
import socket
import connection as c
from constants import *


class Server(object):
    """
    El servidor, que crea y atiende el socket en la dirección y puerto
    especificados donde se reciben nuevas conexiones de clientes.
    """

    def __init__(self, addr=DEFAULT_ADDR, port=DEFAULT_PORT,
                 directory=DEFAULT_DIR):
        print("Serving %s on %s:%s." % (directory, addr, port))
        # NOTE: Crear socket del servidor, configurarlo, asignarlo a una dirección y puerto, etc.
        # 1. Iniciamos variables globales
        self.addr = addr
        self.port = port
        self.directory = directory
        # 2. Creamos socket IPv4 TCP
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # 3. Asociamos el socket a la direccion y puerto especificado
        server_address = (addr, port)
        self.s.bind(server_address)
        # 4. Ponemos al socket en modo servidor escuchando conexiones entrantes
        # TODO: Por ahora el socket solo aceptará una conexión en cola.
        self.s.listen(1)

    def serve(self):
        """
        Loop principal del servidor. Se acepta una conexión a la vez
        y se espera a que concluya antes de seguir.
        """
        try:
            while True:
                sys.stderr.write(
                    'Esperando conexion...\n')
                client_connection, client_address = self.s.accept()
                connect = c.Connection(client_connection, self.directory)
                connect.handle()
        except ValueError as e:
            sys.stderr.write(
                '{} {} {}\n'.format(INTERNAL_ERROR, error_messages[INTERNAL_ERROR], e))
            sys.exit(1)
        finally:
            sys.stderr.write(
                'Closing server... \n')
            self.s.close()


def main():
    """Parsea los argumentos y lanza el server"""

    parser = optparse.OptionParser()
    parser.add_option(
        "-p", "--port",
        help="Número de puerto TCP donde escuchar", default=DEFAULT_PORT)
    parser.add_option(
        "-a", "--address",
        help="Dirección donde escuchar", default=DEFAULT_ADDR)
    parser.add_option(
        "-d", "--datadir",
        help="Directorio compartido", default=DEFAULT_DIR)

    options, args = parser.parse_args()
    if len(args) > 0:
        parser.print_help()
        sys.exit(1)
    try:
        port = int(options.port)
    except ValueError:
        sys.stderr.write(
            "Numero de puerto invalido: %s\n" % repr(options.port))
        parser.print_help()
        sys.exit(1)

    server = Server(options.address, port, options.datadir)
    server.serve()


if __name__ == '__main__':
    main()
