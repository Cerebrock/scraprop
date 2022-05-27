### Scraper para propiedades

Scrapea links a propiedades y manda por Telegram. Por ahora soporta Facebook Marketplace, ZonaProp, ArgenProp, y Mercadolibre hasta donde sé.

## Instrucciones: 

0. Instalar python y las librerías necesarias
2. Completar las variables de entorno en el archivo `.env`
2. Poner URLs con las búsquedas en el archivo `urls_to_scrap.txt`. 
3. Ejecutar con `python scraprop.py`. Va a generar un archivo .txt con los links visitados, y enviar los links nuevos por mensaje.

Ejemplo con el cron que uso: 

```30 */6 * * * /home/cerebrock/anaconda3/bin/python "/home/cerebrock/MyStuff/Programas Varios/scraprop/scraprop.py" >> "/home/cerebrock/MyStuff/Programas Varios/scraprop/logs/scraprop-cron.log" ```

