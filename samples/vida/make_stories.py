"""Seis historias nuevas de ficción: giros de vida y de trabajo (turning point).

Todo es inventado: sin empresas, marcas ni personas reales, y sin ligarlo a noticias o eventos concretos.
"""

import json
from pathlib import Path

STORIES = [
    (
        "Mi casero se quedó con mi depósito",
        "un casero que se queda con el depósito de un inquilino",
        ["casero", "depositodealquiler", "derechosdelinquilino"],
        """Viví tres años en un apartamento pequeño pero lindo. Pagué cada mes a tiempo, cuidé las paredes y hasta pinté la sala con mi propio dinero. Cuando me mudé, mi casero, el señor Gómez, me pidió que dejara las llaves en su buzón. «El depósito te llega en quince días», prometió. Pasaron quince días. Después, treinta. Le escribí. Me contestó con un audio: «Hubo daños, descontamos todo». No me envió una sola foto. Dijo que el piso estaba rayado, que las paredes necesitaban pintura nueva y que la cocina estaba sucia. Me quedé helado. Yo había dejado ese lugar impecable. Mi depósito eran mil doscientos dólares. Pensé en dejarlo así, porque pelear parecía un dolor de cabeza. Pero esa noche, ordenando mi celular para liberar espacio, encontré algo en mi galería. Una carpeta que casi borro por error. Tenía ciento ochenta fotos con fecha. Las había tomado el último día, solo por nostalgia.""",
        """Abrí las fotos una por una. Se veía todo: el piso sin rayones, las paredes recién pintadas, la cocina limpia. Cada imagen tenía la fecha y la hora en los datos del archivo. Escribí un mensaje al señor Gómez, sin enojo. Le dije que tenía fotos de cada espacio tomadas el día de la entrega y que, si el depósito no llegaba en cinco días, presentaría una reclamación formal con ellas. Esa noche contestó rápido, con un tono muy distinto: «Podemos revisarlo». Le respondí que no había nada que revisar, porque ya tenía las pruebas. Al día siguiente me llamó. Dijo que había sido un malentendido con el encargado de limpieza. Esa misma tarde me depositó los mil doscientos dólares completos y hasta un poco más por las molestias. Unas semanas después, un amigo me contó que el señor Gómez le había hecho lo mismo a otros tres inquilinos. Ninguno tenía fotos. Desde ese día, cada vez que entrego o recibo un lugar, lo grabo todo. Porque una foto a tiempo vale más que mil discusiones.""",
    ),
    (
        "Mi compañero de piso alquilaba mi cuarto a escondidas",
        "un compañero de apartamento que subarrienda el cuarto del otro",
        ["roommates", "alquiler", "traicion"],
        """Me fui dos semanas de viaje por trabajo y dejé mi cuarto como siempre. Mi compañero de piso, Daniel, y yo nos llevábamos bien, o eso creía. Al volver, una noche, llegué más temprano de lo esperado. Abrí la puerta del apartamento con cuidado. Había una maleta desconocida en la sala. Y alguien cantando en la ducha. No era Daniel. Mi corazón se aceleró. Caminé hasta mi cuarto y vi la puerta entreabierta. Adentro, mi cama estaba deshecha, con unas sábanas que no eran mías. Sobre mi escritorio había un cargador extraño y una taza usada. Alguien había dormido en mi cuarto. Salió de la ducha un chico con una toalla y se quedó mirándome, pálido. «¿Tú quién eres?», me preguntó. «Yo vivo aquí», le dije. Los dos nos quedamos callados. Entonces apareció Daniel en la puerta, con la cara blanca como el papel, y dijo algo que yo no esperaba.""",
        """«Puedo explicarlo». Daniel confesó que estaba muy endeudado y que había publicado mi cuarto en una página de alquileres cortos, por noches, sin avisarme. Ya llevaba tres viajes míos haciéndolo. Me quedé mirándolo sin poder hablar. El chico de la toalla pidió disculpas: había pagado por una noche sin saber nada. Lo dejé recoger sus cosas y le pedí que no se preocupara, que él no tenía la culpa. Después me senté con Daniel. No le grité. Le dije que quería ver todo el registro de lo que había cobrado. Eran casi novecientos dólares. Le dije que tenía dos opciones: devolverme todo ese dinero esa misma semana o hablar con el dueño del apartamento. Pagó en cinco días. Pero no pude seguir viviendo con él. Le pedí al dueño que pusiera el contrato solo a mi nombre, y busqué a otra persona de confianza para compartir. Daniel se mudó al mes. Lo que más me dolió no fue el dinero. Fue que me sonreía todas las noches mientras me ocultaba esto. Desde entonces, la confianza la doy despacio, y mi cuarto tiene llave.""",
    ),
    (
        "El vendedor me juró que el carro tenía pocos kilómetros",
        "un vendedor de carros usados que alteró el kilometraje",
        ["autousado", "estafa", "consejos"],
        """Mi primer carro lo compré usado, con todos mis ahorros. El vendedor, un señor muy simpático, me dijo: «Solo tiene cuarenta mil kilómetros, lo usaba una señora para ir a misa». El tablero marcaba justo eso. El precio era bueno, demasiado bueno. Yo estaba emocionado y quería cerrar el trato ese mismo día. Pero mi tío me había dicho algo antes de salir de casa: «Nunca compres un carro sin que lo vea un mecánico». Le pedí al vendedor que me dejara llevar el carro a una revisión. Se puso nervioso. Dijo que otro comprador venía esa tarde y que no podía esperar. «Si te lo piensas, se lo lleva el otro», insistió. Sentí la presión en el pecho. Pero algo en su prisa me incomodó. Le dije que volvería en una hora, con un mecánico. Llamé a Jorge, el mecánico de mi tío, y le pedí que me acompañara. Cuando llegamos, Jorge se agachó junto al pedal del freno, lo miró un segundo y negó con la cabeza.""",
        """«Mira esto», me dijo Jorge. El pedal estaba gastado hasta el metal, algo que solo pasa después de muchísimos kilómetros. Luego abrió la puerta del conductor y señaló el asiento, hundido y desgastado. «Este carro tiene más de doscientos mil kilómetros», dijo. Conectó una máquina de diagnóstico y me mostró la memoria del computador, donde quedaba guardado el kilometraje real. Doscientos diez mil. El tablero había sido alterado. Miré al vendedor, que ya no sonreía. Le dije con calma lo que habíamos encontrado. Primero negó todo. Luego dijo que él no sabía, que se lo había comprado así a otra persona. Le dije que me iba, y que si publicaba ese carro con el mismo kilometraje, lo denunciaría. No le compré nada ese día, pero no perdí mis ahorros. Una semana después, Jorge me encontró otro carro, más viejo en apariencia, pero con el historial limpio y el kilometraje real. Costó lo mismo y todavía lo tengo. Desde entonces se lo repito a todos mis amigos: antes de comprar, un mecánico y una máquina de diagnóstico valen más que cualquier sonrisa.""",
    ),
    (
        "Me llegó por error el mensaje de mi jefe",
        "un mensaje de la empresa enviado por error sobre despidos",
        ["despidos", "trabajo", "giroinesperado"],
        """Un jueves por la tarde, mi jefe escribió en el chat del equipo un mensaje que no era para nosotros. Duró treinta segundos y lo borró, pero yo alcancé a leerlo completo. Decía: «El viernes de la próxima semana comunicamos los despidos. Que nadie se entere antes, no queremos que se vayan los mejores». Sentí un frío por todo el cuerpo. Trabajaba allí hacía cuatro años y tenía un crédito del banco por pagar. Miré a mis compañeros alrededor. Algunos reían, ajenos a todo. Pensé en decirles, pero si lo hacía, me delataría. Pensé en fingir que no vi nada. Esa noche no pude dormir. Al día siguiente, mi jefe pasó junto a mi escritorio y me dijo, con su mejor sonrisa: «Qué bien te va con el proyecto nuevo». No sabía si estaba en la lista. Decidí que no me quedaría esperando a ver qué pasaba. Esa misma noche abrí mi computador y empecé a hacer algo que cambió mi suerte.""",
        """Actualicé mi currículum y le pedí a tres personas que me dieran una carta de recomendación. Durante esa semana contesté llamadas de reclutadores en mi hora de almuerzo. Fui a dos entrevistas con la excusa de citas médicas. El miércoles recibí una oferta formal de otra empresa, con un salario un diez por ciento mayor. La acepté por escrito, con fecha de inicio dentro de tres semanas. El viernes de los despidos llegué temprano, tranquilo. Uno por uno, mis compañeros eran llamados a la sala de reuniones. Cuando me llegó el turno, la jefa de recursos humanos me dijo con tono triste: «Lamentamos informarte que tu puesto se elimina». Le sonreí y le contesté: «Gracias por avisarme. Ya tenía otro trabajo». Su cara se quedó helada. Pedí, además, mi liquidación completa, con todos los beneficios que correspondían a mis cuatro años. La recibí íntegra. Muchos de mis compañeros se fueron sin plan. Yo salí con trabajo nuevo y mi dinero. Nunca le conté a nadie lo del mensaje. Pero aprendí que la información, usada con calma, puede cuidar tu futuro.""",
    ),
    (
        "La oferta que casi acepté con la mitad del sueldo",
        "una oferta de trabajo con funciones de jefe y sueldo de asistente",
        ["entrevista", "negociacion", "giroinesperado"],
        """Después de seis meses sin trabajo, me llamaron de una empresa grande. La entrevista fue perfecta, o eso pensé. Al final el gerente me dijo: «Tenemos un problema: el puesto que pensabas ya no existe, pero te ofrecemos otro con menos sueldo». Era un treinta por ciento menos de lo prometido. Me quedé callado. Necesitaba el empleo. Mi pareja me miraba preocupada cada noche. Aun así, había algo en la oferta que no me gustaba. Pedí el contrato por escrito antes de decidir. Me llegó al día siguiente. Leí con calma. El puesto se llamaba «analista de apoyo», pero las funciones eran las de un jefe de área: dirigir a cinco personas, responder por resultados y viajar. Todo con sueldo de asistente. Le conté a mi mejor amiga, que trabaja en recursos humanos. Soltó una carcajada seca y me dijo: «Eso es pedir un jefe y pagar un asistente». Me aconsejó algo que yo nunca me habría atrevido a hacer.""",
        """Me dijo que respondiera con un correo educado, pidiendo que el cargo y el sueldo coincidieran con las funciones reales. Si no aceptaban, que dijera que lo agradecía, pero que declinaba. Dudé mucho. Tenía miedo de quedarme sin nada. Pero respiré hondo y lo envié. Cuatro días después, nada. Pensé que había cometido un error. Fui a dormir con un nudo en el estómago. Al día siguiente, a las ocho de la mañana, sonó mi teléfono. Era el gerente. Con voz seria, me dijo: «Tienes razón. Si las funciones son esas, el cargo y el sueldo deben ser los de jefe de área». Me ofreció el puesto de verdad, con un sueldo cuarenta por ciento mayor al de la primera oferta, y un bono. Dijo que le había impresionado que supiera defender mi valor. Acepté. Hoy dirijo ese equipo de cinco personas. Y cada vez que alguien que entrevisto duda si pedir lo justo, le cuento esta historia y le digo que un «no, gracias» a tiempo puede abrir la mejor puerta.""",
    ),
]

if __name__ == "__main__":
    out = Path(__file__).parent
    for i, (title, topic, tags, part1, part2) in enumerate(STORIES, start=1):
        data = {
            "title": title,
            "topic": topic,
            "tags": tags,
            "text": f"{part1.strip()}\n[CORTE]\n{part2.strip()}",
        }
        path = out / f"{i:02d}_historia.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{path.name}: {title} ({len(part1.split())} + {len(part2.split())} palabras)")
