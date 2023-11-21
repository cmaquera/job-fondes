import requests
import pandas as pd
import io
import os
from ftplib import FTP
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# Obtener variables de entorno
HOSTNAME = os.getenv('FTP_HOSTNAME')
USERNAME = os.getenv('FTP_USERNAME')
PASSWORD = os.getenv('FTP_PASSWORD')
ANIO = '2020'

print('{} {} {}'.format(HOSTNAME, USERNAME, PASSWORD))

req_obj = requests.Session()

headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Connection': 'keep-alive',
    'User-Agent': 'python-requests/2.31.0',
}

url_principal = "https://apps5.mineco.gob.pe/seguimiento_fondes/Descarga/DatosAbiertos/Default.aspx"

def obtener_data(response):
    soup_principal = BeautifulSoup(response.content , "lxml")

    hidden_inputs = soup_principal.find_all("input",type="hidden")
    select_inputs = soup_principal.find_all("select")

    data = {
        hidden_inputs[0]['name']: hidden_inputs[0]['value'],
        hidden_inputs[1]['name']: hidden_inputs[1]['value']
    }

    if select_inputs :
        for select in select_inputs:
            element_value = []
            for select_option in select.find_all('option', selected=True):
                element_value.append(select_option['value'])
            data[select['name']] = element_value

    return data


def obtener_data_initial(anio_ejecucion, tipo_gobierno):
    print('Aplicando filtros de periodo {} y tipo de gobierno {}'.format(anio_ejecucion, tipo_gobierno))
    # Consultar la ruta principal para obtener los tokens de aspx
    response_initial = req_obj.get(url_principal)
    soup_principal = BeautifulSoup(response_initial.content , "lxml")

    hidden_inputs = soup_principal.find_all("input",type="hidden")

    # Tokens: 1 => __EVENTVALIDATIO, 0 => __VIEWSTATE
    data = {
        hidden_inputs[0]['name']: hidden_inputs[0]['value'],
        hidden_inputs[1]['name']: hidden_inputs[1]['value'],
        '__EVENTTARGET': 'ctl00$ctl00$CPH1$RptPH1$LstTipoGobierno',
        'ctl00$ctl00$CPH1$RptPH1$LstAnoEje': anio_ejecucion,
        'ctl00$ctl00$CPH1$RptPH1$LstTipoGobierno': tipo_gobierno
    }

    #Consultar los datos de los parametros
    req = requests.Request('POST', url_principal, headers=headers, data=data)
    prepped = req.prepare()

    del prepped.headers['Content-Length']

    response_filter = req_obj.send(prepped)

    return obtener_data(response_filter)

def obtener_data_body(evento, parametro, valor, data):
    print('Aplicando filtros de parametro {} y valor {}'.format(parametro, valor))
    #Remplazar parametro de busqueda
    data[parametro] = valor
    data['__EVENTTARGET']: evento
    
    #Consultar los datos de los parametros para la descarga
    req = requests.Request('POST', url_principal, headers=headers, data=data)
    prepped = req.prepare()

    del prepped.headers['Content-Length']

    response_filter = req_obj.send(prepped)

    return obtener_data(response_filter)

def obtener_csv_data(data):
    print('Obtener datos en formato csv')
    #Configurar data para la descarga
    data['__EVENTTARGET'] = ''
    data['ctl00$ctl00$CPH1$RptPH1$btnExportarCSV'] = 'Exportar a CSV'

    req = requests.Request('POST', url_principal, headers=headers, data=data)
    prepped = req.prepare()

    del prepped.headers['Content-Length']

    response_file = req_obj.send(prepped)

    csv_content = response_file.content

    return pd.read_csv(io.StringIO(csv_content.decode('utf-8')))


def guradar_archivo_filtrado():
    
    ftp_server = FTP(HOSTNAME, USERNAME, PASSWORD)
    filename = 'output.xlsx'

    # Obtener datos Locales
    print('Obtener datos Locales...')
    data_initial = obtener_data_initial(ANIO, 'M')
    df_data_local = obtener_csv_data(data_initial)    

    # Obtener datos Regionales
    print('Obtener datos Regionales...') 
    data_initial = obtener_data_initial(ANIO, 'R')
    data_body = obtener_data_body('ctl00$ctl00$CPH1$RptPH1$lstSector', 'ctl00$ctl00$CPH1$RptPH1$lstSector', '99', data_initial)
    df_data_regional = obtener_csv_data(data_body)

    # Obtener datos Nacionales    
    print('Obtener datos Nacionales...') 
    data_initial = obtener_data_initial(ANIO, 'E')
    data_body = obtener_data_body('ctl00$ctl00$CPH1$RptPH1$lstSector', 'ctl00$ctl00$CPH1$RptPH1$lstSector', ['26', '36'], data_initial)
    data_body = obtener_data_body('ctl00$ctl00$CPH1$RptPH1$lstPliego', 'ctl00$ctl00$CPH1$RptPH1$lstPliego', ['026', '036'], data_body)
    data_body = obtener_data_body('ctl00$ctl00$CPH1$RptPH1$lstEjecutora', 'ctl00$ctl00$CPH1$RptPH1$lstEjecutora', ['470', '1072', '1078', '1250'], data_body)
    df_data_nacional = obtener_csv_data(data_body)

    print('Uniendo datos en un archivo Exel...')
    df_csv = pd.concat([df_data_local, df_data_regional, df_data_nacional])

    df_csv.to_excel(filename, index=False)

    # Guardar archivo en el servidor FTP    
    print('Guardado de archivo en servidor ftp')
    # forzaar UTF-8 encoding
    ftp_server.encoding = "utf-8"
    # Leer archivo y aguardar en el servidodr
    with open(filename, "rb") as file:
        # comando para guardar archivo "STOR filename"
        ftp_server.storbinary(f"STOR {filename}", file)
    
    ftp_server.quit()


import timeit
from datetime import datetime

print('Proceso iniciado - {}'.format(datetime.now()))

segundos = timeit.timeit(lambda: guradar_archivo_filtrado(), number=1)

print('Proceso finalizado - {}'.format(datetime.now()))
print('Tiempo de ejecución - {} segundos'.format(segundos))
 

