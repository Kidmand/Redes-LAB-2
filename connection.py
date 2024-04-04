# encoding: utf-8
# Revisión 2019 (a Python 3 y base64): Pablo Ventura
# Copyright 2014 Carlos Bederián
# $Id: connection.py 455 2011-05-01 00:32:09Z carlos $

import sys
import socket
from constants import *
from base64 import b64encode


class Connection(object):
    """
    Conexión punto a punto entre el servidor y un cliente.
    Se encarga de satisfacer los pedidos del cliente hasta
    que termina la conexión.
    """

    def __init__(self, socket, directory):
        # NOTE: Inicializar atributos de Connection
        self.socket = socket
        self.directory = directory
        self.connected = True

    def handle(self):
        """
        Atiende eventos de la conexión hasta que termina.
        """
        try:
            local_address = self.socket.getsockname()

            sys.stdout.write('Conected by: %s \n' % str(local_address))

            # Recibe los datos en trozos y atiende los eventos
            while self.connected:
                data = self.socket.recv(19)
                sys.stdout.write('recibido "%s" \n' % data)
                if data:
                    self._satisfacer_pedido(data)
                else:
                    sys.stdout.write('No hay mas datos.\n')
                    break
        except ValueError as e:
            mensaje = '{} {} \n'.format(*e.args)
            self.socket.sendall(mensaje.encode())
        finally:
            sys.stdout.write(
                'Closing connection... \n')
            self.socket.close()

    def _satisfacer_pedido(self, data):
        """
        Determina el pedido que contiene el parametro DATA y redirecciona al metodo que se encarga de satisfacerlo.
        """
        pedido = data.replace(b"\r\n", b"").decode()
        match pedido:
            case "get_slice":
                self._get_slice()
            case "get_metadata":
                self._get_metadata()
            case "get_file_listing":
                self._get_file_listing()
            case "quit":
                self._quit()
            case _:
                raise ValueError(
                    INVALID_COMMAND, error_messages[INVALID_COMMAND])

    def _quit(self):
        """
        Termina la conexión.
        El servidor responde con un resultado exitoso (0 OK) y cierra la conexion.
        """
        mensaje = '{} {} \n'.format(CODE_OK, error_messages[CODE_OK])
        self.socket.sendall(mensaje.encode())
        self.connected = False

    def _get_slice(self, filename, offset, size):
        """
        Este comando recibe en el argumento FILENAME el nombre de archivo del que se pretende obtener un slice o parte. 
        La parte se especifica con un OFFSET (byte de inicio) y un SIZE (tamaño de la parte esperada, en bytes), ambos no negativos. 
        El servidor responde con el fragmento de archivo pedido codificado en base64 y un \r\n.
        Byte:      0    5    10   15   20   25   30   35   40
           v    v    v    v    v    v    v    v    v  
        Archivo:   !Que calor que hace hoy, pinta una birra!
        Comando:   get_slice archivo.txt 5 20
        Respuesta: 0 OK\r\n
           Y2Fsb3IgcXVlIGhhY2UgaG95LCA=\r\n2
           """
        pass

    def _get_metadata(self, filename):
        """
        Este comando recibe un argumento FILENAME especificando un nombre de archivo del cual se pretende averiguar el tamaño. 
        El servidor responde con una cadena indicando su valor en bytes.

        Ejemplo: 
        Comando:   get_metadata archivo.txt
        Respuesta: 0 OK\r\n
           3199\r\n
           """
        pass

    def _get_file_listing(self):
        """
        Busca obtener la lista de archivos que están actualmente disponibles.
        El servidor responde con una secuencia de líneas terminadas en \r\n, cada una con el nombre de uno de los archivos disponible. 
        Una línea sin texto indica el fin de la lista.

        Ejemplo: 
        Comando:   get_file_listing
        Respuesta: 0 OK\r\n
           archivo1.txt\r\n
           archivo2.jpg\r\n
           \r\n
        """
        pass


"""
python3 server.py
telnet 0.0.0.0 19500
"""
