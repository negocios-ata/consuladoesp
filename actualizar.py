#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Actualiza fechas.json leyendo el TEXTO de los canales de Telegram.

No usa imágenes ni OCR: solo el texto de los mensajes.
Lo que hace está en canales_texto.py; este archivo existe para que la Action
tenga un único punto de entrada.
"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import canales_texto  # noqa: E402

if __name__ == "__main__":
    sys.exit(canales_texto.main())
