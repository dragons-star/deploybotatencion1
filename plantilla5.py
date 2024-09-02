import logging
import datetime
import pytz
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, CallbackContext

# Configuración básica del logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Lista para almacenar las citas
citas = []

# Función para enviar correos electrónicos
def enviar_correo(destinatario, nombre, fecha_hora, asunto, cuerpo):
    remitente = "registropruebas33@gmail.com"  # Cambia a tu dirección de correo
    password = "ztxhnzozblgtcnps"  # Cambia a tu contraseña
    
    # Configuración del contenido del correo
    msg = MIMEMultipart()
    msg['From'] = remitente
    msg['To'] = destinatario
    msg['Subject'] = asunto
    msg.attach(MIMEText(cuerpo, 'plain'))
    
    try:
        # Conexión al servidor SMTP de Gmail
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remitente, password)
        texto = msg.as_string()
        server.sendmail(remitente, destinatario, texto)
        server.quit()
        print(f"Correo enviado a {destinatario}")
    except Exception as e:
        print(f"Error al enviar correo: {e}")

# Función para mostrar el menú principal
async def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("Agendar Cita", callback_data='agendar')],
        [InlineKeyboardButton("Cancelar Cita", callback_data='cancelar')],
        [InlineKeyboardButton("Ver Citas", callback_data='ver_citas')],
        [InlineKeyboardButton("Ayuda", callback_data='ayuda')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Bienvenido al centro estético. Selecciona una opción:", reply_markup=reply_markup)

# Función para manejar la selección del menú
async def button(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    action = query.data

    if action == 'agendar':
        await mostrar_calendario(query, context)
        context.user_data['action'] = 'agendar'
    elif action == 'cancelar':
        await query.edit_message_text("Por favor, proporciona la fecha y hora de la cita que deseas cancelar (YYYY-MM-DD hh:mm AM/PM o YYYY-MM-DD HH:mm).")
        context.user_data['action'] = 'cancelar'
    elif action == 'ver_citas':
        await query.edit_message_text(ver_citas())
    elif action == 'ayuda':
        await query.edit_message_text("Para agendar una cita, selecciona 'Agendar Cita'. Para cancelar, selecciona 'Cancelar Cita'. Puedes ver tus citas seleccionando 'Ver Citas'.")
    elif action.startswith('fecha_'):
        fecha_str = action.replace('fecha_', '')
        fecha = datetime.datetime.strptime(fecha_str, '%Y-%m-%d').date()
        context.user_data['fecha'] = fecha  # Guardar la fecha seleccionada
        await mostrar_horarios_disponibles(query, context, fecha)
    elif action.startswith('hora_'):
        await manejar_horario_seleccionado(query, context)

# Función para mostrar el calendario
async def mostrar_calendario(update, context):
    ahora = datetime.datetime.now(pytz.timezone('America/Bogota'))
    fecha_actual = ahora.date()
    fechas = [fecha_actual + datetime.timedelta(days=i) for i in range(7)]  # Muestra los próximos 7 días

    keyboard = []
    for fecha in fechas:
        keyboard.append([InlineKeyboardButton(fecha.strftime('%Y-%m-%d'), callback_data=f'fecha_{fecha.strftime("%Y-%m-%d")}')])

    keyboard.append([InlineKeyboardButton("Cancelar", callback_data='cancelar')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Selecciona una fecha para agendar la cita:", reply_markup=reply_markup)

# Función para mostrar horarios disponibles en una fecha seleccionada
async def mostrar_horarios_disponibles(query, context, fecha):
    hora_inicio = datetime.time(8, 0)
    hora_fin = datetime.time(18, 0)

    horarios = []

    while hora_inicio <= hora_fin:
        fecha_hora = datetime.datetime.combine(fecha, hora_inicio, tzinfo=pytz.timezone('America/Bogota'))
        if not verificar_cita_existe(fecha_hora):
            hora_str = fecha_hora.strftime('%I:%M %p')  # Formato de 12 horas
            horarios.append((hora_str, fecha_hora))
        
        hora_inicio = (datetime.datetime.combine(fecha, hora_inicio) + datetime.timedelta(minutes=30)).time()

    if not horarios:
        await query.message.reply_text(f"No hay horarios disponibles para {fecha.strftime('%Y-%m-%d')}.")
        return

    horarios.sort(key=lambda x: x[1])

    keyboard = [[InlineKeyboardButton(hora_str, callback_data=f'hora_{hora_str}')] for hora_str, _ in horarios]
    keyboard.append([InlineKeyboardButton("Cancelar", callback_data='cancelar')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(f"Selecciona una hora disponible para {fecha.strftime('%Y-%m-%d')}:", reply_markup=reply_markup)

# Función para manejar la selección del horario
async def manejar_horario_seleccionado(query, context):
    hora_str = query.data.replace('hora_', '')
    fecha = context.user_data.get('fecha')  # Obtener la fecha seleccionada previamente

    if not fecha:
        await query.message.reply_text("Error: No se ha seleccionado una fecha.")
        return

    fecha_hora = datetime.datetime.strptime(hora_str, '%I:%M %p').time()
    fecha_hora = datetime.datetime.combine(fecha, fecha_hora, tzinfo=pytz.timezone('America/Bogota'))
    
    ahora = datetime.datetime.now(pytz.timezone('America/Bogota'))
    
    if fecha_hora <= ahora:
        await query.message.reply_text("No puedes agendar una cita en el pasado. Por favor, elige una fecha y hora futuras.")
        return

    context.user_data['fecha_hora'] = fecha_hora
    await query.message.reply_text("Por favor, proporciona tu nombre, teléfono y email, separados por comas.")
    context.user_data['action'] = 'confirmar_agendar'

# Función para mostrar las citas agendadas
def ver_citas():
    if not citas:
        return "No hay citas agendadas."
    else:
        response = "Citas agendadas:\n\n"
        for i, cita in enumerate(citas, start=1):
            response += f"{i}. {cita['fecha_hora'].strftime('%Y-%m-%d %I:%M %p')} - {cita['nombre']} ({cita['telefono']})\n"
        return response

# Función para verificar si ya existe una cita en una fecha y hora específicas
def verificar_cita_existe(fecha_hora):
    for cita in citas:
        if cita['fecha_hora'] == fecha_hora:
            return True
    return False

# Función para manejar mensajes del usuario
async def handle_message(update: Update, context: CallbackContext):
    text = update.message.text.strip()
    action = context.user_data.get('action')

    saludos = ['hola', 'buenas tardes', 'buenos días', 'saludos', 'buenas noches']

    if any(saludo in text.lower() for saludo in saludos):
        await update.message.reply_text("¡Hola! Bienvenido al centro estético.")
        await start(update, context)  # Mostrar el menú

    elif "agendar" in text.lower() or "agendar cita" in text.lower():
        await mostrar_calendario(update, context)
        context.user_data['action'] = 'agendar'

    elif "ver" in text.lower():
        await update.message.reply_text(ver_citas())
        context.user_data['action'] = None

    elif "ayuda" in text.lower():
        await update.message.reply_text("Para agendar una cita, selecciona 'Agendar Cita'. Para cancelar, selecciona 'Cancelar Cita'. Puedes ver tus citas seleccionando 'Ver Citas'.")
        context.user_data['action'] = None

    elif action == 'confirmar_agendar':
        try:
            datos = text.split(',')
            if len(datos) != 3:
                raise ValueError("Formato incorrecto. Asegúrate de usar el formato: Nombre, Teléfono, Email.")
            
            nombre = datos[0].strip()
            telefono = datos[1].strip()
            email = datos[2].strip()
            fecha_hora = context.user_data.get('fecha_hora')

            if not es_fecha_valida(fecha_hora):
                await update.message.reply_text("La fecha y hora deben ser futuras.")
                return

            if verificar_cita_existe(fecha_hora):
                await update.message.reply_text("Ya hay una cita agendada en ese horario.")
            else:
                cita = {
                    'fecha_hora': fecha_hora,
                    'nombre': nombre,
                    'telefono': telefono,
                    'email': email
                }
                citas.append(cita)
                await update.message.reply_text(f"Cita agendada para {fecha_hora.strftime('%Y-%m-%d %I:%M %p')}.\nTe enviaremos un recordatorio por correo.")
                enviar_correo(email, nombre, fecha_hora, "Confirmación de Cita", f"Hola {nombre}, tu cita está agendada para {fecha_hora.strftime('%Y-%m-%d %I:%M %p')}.")
                
        except ValueError as e:
            await update.message.reply_text(str(e))
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    elif action == 'cancelar':
        try:
            datos = text.split()
            if len(datos) != 2:
                await update.message.reply_text("Por favor, proporciona la fecha y hora de la cita (YYYY-MM-DD hh:mm AM/PM o YYYY-MM-DD HH:mm).")
                return

            fecha_str = datos[0]
            hora_str = datos[1]
            fecha_hora_str = f"{fecha_str} {hora_str}"

            # Intentar con el formato de 12 horas
            try:
                fecha_hora = datetime.datetime.strptime(fecha_hora_str, '%Y-%m-%d %I:%M %p')
            except ValueError:
                # Si falla, intentar con el formato de 24 horas
                fecha_hora = datetime.datetime.strptime(fecha_hora_str, '%Y-%m-%d %H:%M')

            fecha_hora = pytz.timezone('America/Bogota').localize(fecha_hora)

            cita_encontrada = False
            for cita in citas:
                if cita['fecha_hora'] == fecha_hora:
                    citas.remove(cita)
                    await update.message.reply_text(f"Cita para {fecha_hora.strftime('%Y-%m-%d %I:%M %p')} cancelada.")
                    enviar_correo(cita['email'], cita['nombre'], fecha_hora, "Cancelación de Cita", f"Hola {cita['nombre']}, tu cita programada para {fecha_hora.strftime('%Y-%m-%d %I:%M %p')} ha sido cancelada.")
                    cita_encontrada = True
                    break

            if not cita_encontrada:
                await update.message.reply_text("No se encontró una cita en esa fecha y hora.")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

# Función para validar si una fecha es válida
def es_fecha_valida(fecha_hora):
    ahora = datetime.datetime.now(pytz.timezone('America/Bogota'))
    return fecha_hora > ahora

def main():
    # Aquí deberás colocar tu token de Telegram
    TOKEN = '7530011537:AAH7woWULberXS2NJN5lj5siMb0oKQo_F38'

    application = Application.builder().token(TOKEN).build()

    # Manejadores de comandos
    application.add_handler(CommandHandler('start', start))

    # Manejadores de mensajes
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Manejadores de botones
    application.add_handler(CallbackQueryHandler(button))

    # Ejecutar el bot
    application.run_polling()

if __name__ == '__main__':
    main()
