"""Seis historias nuevas de ficción sobre temas laborales que se repiten en redes (quiet firing, act your wage,
IA y empleo, regreso a la oficina, ghosting de reclutadores, transparencia salarial).

Todo es inventado: sin empresas, marcas ni personas reales, y sin ligarlo a noticias o eventos concretos.
"""

import json
from pathlib import Path

STORIES = [
    (
        "Me despidieron sin decírmelo",
        "quiet firing: una jefa que te deja sin trabajo para que renuncies",
        ["quietfiring", "jefetoxico", "derechoslaborales"],
        """Un lunes mi jefa dejó de invitarme a las reuniones. Pensé que fue un descuido. El martes me quitó mi proyecto principal y me dijo que lo iba a llevar otra persona. El miércoles ya no me asignaba nada. Yo llegaba a la oficina y pasaba ocho horas mirando la pantalla. Cuando preguntaba por trabajo, ella contestaba: «Todavía no hay nada para ti». Mis compañeros empezaron a evitarme en el pasillo. Una amiga me explicó que eso tenía nombre: querían que yo renunciara solo, para no pagarme la liquidación. Me sentí humillado. Pasé tres semanas así, hasta que una tarde vi algo por casualidad. En la impresora había una hoja olvidada. Era un correo interno de mi jefa para recursos humanos. Decía: «Si lo ignoramos lo suficiente, se va solo. Así nos ahorramos el pago». Se me heló la sangre. Tenía la prueba escrita en mis manos. Pero ¿qué hacía con ella?""",
        """Doblé la hoja y la guardé en mi bolso. Esa noche investigué qué decía la ley sobre mi caso. Aprendí que provocar la renuncia a propósito se puede considerar un despido disfrazado. Al día siguiente pedí una reunión formal con recursos humanos, y la pedí por escrito, para que quedara registro. Llegué con la hoja, mis correos sin respuesta y una lista de todas las tareas que me habían quitado. La responsable de recursos humanos leyó el papel en silencio. Cambió de color. «Esto no debió salir de aquí», murmuró. Le respondí con calma: «Entonces hablemos de cómo se arregla». Esa misma semana, mi jefa fue llamada a explicar su correo. Yo recibí dos opciones. Podía volver a mi puesto con todas mis funciones, o recibir una indemnización completa más tres meses extra. Elegí la indemnización. Con ese dinero tomé un curso y conseguí un trabajo mejor en dos meses. Mi jefa fue trasladada a otro departamento. Y yo aprendí que, cuando alguien quiere sacarte sin pagarte, lo más peligroso para él es que tú guardes los papeles.""",
    ),
    (
        "Hice solo lo que decía mi contrato",
        "act your wage: dejar de trabajar gratis",
        ["actyourwage", "trabajo", "limites"],
        """Durante dos años trabajé gratis sin darme cuenta. Mi contrato decía de nueve a cinco, pero yo llegaba a las ocho y salía a las siete. Contestaba mensajes los domingos. Cubría a compañeros que se iban temprano. Mi jefe lo llamaba compromiso. Una vez le pedí un aumento. Se rió y me dijo: «Si quieres crecer, primero demuestra más». No entendí cómo podía demostrar más de lo que ya hacía. Una noche, agotado, leí mi contrato completo. Decía que mis funciones eran seis. Seis. Yo hacía como quince. Decidí hacer un experimento. Al día siguiente llegué a las nueve, hice mis seis funciones y a las cinco en punto apagué mi computador. Sin drama, sin quejas. Mi jefe me miró raro. «¿Pasó algo?», me preguntó. «No», le dije. «Solo estoy cumpliendo mi contrato». Ese viernes, a las cuatro de la tarde, empezaron las llamadas de pánico. Y todo se vino abajo.""",
        """La primera semana, lo que yo antes hacía sin que nadie lo notara empezó a fallar. Los reportes salían tarde. Los clientes esperaban respuestas. Mi jefe se iba poniendo nervioso. Al final de la segunda semana me llamó a su oficina. Estaba pálido. «Necesito que vuelvas a hacer lo que hacías antes», me dijo. Yo respiré hondo y le contesté: «Con gusto, pero hablemos de ese trabajo extra y de su pago». Se quedó callado. Le pasé una hoja con la lista de las nueve tareas que hacía sin cobrarlas, con el tiempo que me tomaba cada una. Al lado puse una cifra. No era una exigencia, era una cuenta. Pasaron tres días y recibí una respuesta: ascenso a coordinador, con un aumento del treinta y cinco por ciento, y dos personas a mi cargo para repartir el trabajo. Acepté. Lo curioso es que mi vida cambió mucho. Ahora salgo a las cinco, y la empresa funciona mejor que antes. A veces, hacer lo que te corresponde es la mejor forma de que valoren lo que haces de más.""",
    ),
    (
        "Me pidieron entrenar a la IA que me iba a reemplazar",
        "una empresa que quiere reemplazar a una empleada con inteligencia artificial",
        ["ia", "inteligenciaartificial", "futurodeltrabajo"],
        """Un martes mi jefe me reunió con una sonrisa enorme. «Vamos a implementar una herramienta de inteligencia artificial», dijo. «Y quiero que tú la entrenes, porque nadie conoce el proceso como tú». Me sentí halagada. Durante un mes le enseñé todo: cómo respondo a los clientes, cómo resuelvo los casos difíciles, mis atajos y mis trucos. Documenté cada paso. Hasta que, un día, vi la agenda compartida de mi jefe por error. Tenía una reunión llamada «Plan de transición del equipo de atención». Abrí el archivo adjunto. Era una tabla con los nombres de mi equipo. Al lado de cada uno había una fecha y una palabra: «salida». La mía era la primera, en dos meses. Entendí de golpe para qué quería que entrenara a la herramienta. Me temblaron las manos. Estaba construyendo mi propia salida. Pero esa noche, mirando el techo, se me ocurrió una idea que cambió todo.""",
        """Al día siguiente no me quejé. Seguí entrenando a la herramienta, pero también empecé a registrar sus errores. Cada vez que fallaba en un caso difícil, yo lo anotaba con la fecha, la queja del cliente y el costo para la empresa. En dos semanas tenía un informe de treinta páginas. Lo presenté a mi jefe como mejoras necesarias. Él lo leyó muy serio. «No sabía que fallaba tanto», admitió. Entonces le hice una propuesta. Yo no iba a competir contra la herramienta, iba a supervisarla. Con ella resolviendo lo simple y yo los casos complejos, la empresa ahorraba tiempo sin perder clientes. Le puse números y plazos. Pensó un momento largo. Aceptó. Mi puesto cambió de nombre: responsable de calidad y automatización, con mejor sueldo. De mi equipo, la mitad se quedó, con funciones nuevas. Aprendí que las herramientas no reemplazan a quien sabe usarlas bien. Reemplazan a quien se queda esperando a que lo reemplacen.""",
    ),
    (
        "Nos obligaron a volver a la oficina",
        "una empresa que obliga a volver a la oficina por una razón escondida",
        ["trabajoremoto", "oficina", "cultura"],
        """Llevábamos tres años trabajando desde casa y todo funcionaba perfecto. Hasta que llegó el correo del director: «A partir del primero de mes, todos regresan a la oficina, cinco días a la semana». Nadie entendía por qué. Los resultados eran buenos, los clientes estaban felices. Pregunté en la reunión y el director respondió: «Es por la cultura de la empresa». Algo no me cerraba. Una semana antes, mi amiga de contabilidad me había comentado que la empresa seguía pagando un edificio enorme, casi vacío. «Pagamos el arriendo de todo el piso nueve y diez», me dijo, «y nadie va». Yo hice la cuenta en mi cabeza. Ese contrato era carísimo. Una noche, ayudando a mi amiga con unos archivos, abrí por accidente un documento llamado «Cláusula de ocupación mínima». Lo leí con el corazón acelerado. Y ahí, en una línea, estaba la verdadera razón de todo.""",
        """La cláusula decía que, si la ocupación del edificio bajaba del sesenta por ciento, la empresa perdía un descuento enorme en el arriendo. Es decir, no nos obligaban a volver por la cultura. Nos obligaban para no perder dinero. Me quedé pensando qué hacer. Si lo contaba a gritos, me iba a ganar un problema. Así que hablé con mis compañeros, con calma, uno por uno. Juntos escribimos una propuesta formal y muy respetuosa. Proponía tres días en la oficina y dos en casa, lo que alcanzaba el sesenta por ciento de ocupación sin obligar a nadie a ir los cinco días. Incluimos los resultados de los últimos tres años y el ahorro que traía el trabajo remoto. La enviamos firmada por cuarenta personas. El director nos citó, con cara de pocos amigos. Pero leyó los números y se quedó callado. Una semana después llegó el correo nuevo: tres días de oficina y dos remotos. Nadie renunció. Y yo entendí que, muchas veces, un buen argumento escrito con respeto pesa más que una queja.""",
    ),
    (
        "Cinco entrevistas y me dejaron en visto",
        "una empresa que deja en visto a un candidato después de cinco entrevistas",
        ["ghosting", "entrevistadetrabajo", "busquedadeempleo"],
        """Pasé cinco entrevistas para el mismo puesto. Cinco. La primera con recursos humanos, la segunda con el jefe, la tercera con el equipo, una prueba técnica y una última con el director. En todas me dijeron lo mismo: «Eres justo lo que buscamos». Al final, el director me estrechó la mano y dijo: «Te escribimos esta semana con la oferta». Salí flotando. Esa semana, nada. La siguiente, tampoco. Les escribí un correo amable, sin respuesta. Llamé, y la recepcionista dijo que me devolverían la llamada. Nunca lo hicieron. Después de un mes entendí que me habían dejado en visto, después de dedicarles veinte horas de mi vida. Me dolió más de lo que quería admitir. Dejé de buscar durante unos días. Hasta que, por pura casualidad, una amiga me mostró una publicación de esa misma empresa. Estaban buscando otra vez, para el mismo puesto. Pero esta vez, el sueldo era treinta por ciento más alto.""",
        """Me quedé mirando la publicación un buen rato. Entonces tuve una idea. No me iba a quejar ni a suplicar. Escribí un correo corto y cordial al director. Le dije que había visto que el puesto estaba abierto otra vez, que seguía interesado, y que, por mi experiencia en el proceso, quería hacer una sola pregunta: ¿el nuevo sueldo era el de la oferta que me habían prometido? Envié el correo un viernes. El lunes, a primera hora, sonó mi teléfono. Era el director en persona. Se disculpó. Me contó que la empresa había congelado las contrataciones por un cambio de presupuesto y que nadie avisó a los candidatos. «Fue un error nuestro», dijo. Me ofreció el puesto, con el sueldo nuevo, y empezar en dos semanas. Lo acepté, pero con una condición: que después de mi primer mes, revisáramos cómo la empresa trata a los candidatos. Hoy dirijo ese proceso de selección. Y a cada persona que entrevisto le respondo siempre, aunque sea para decirle que no.""",
    ),
    (
        "Supe cuánto ganaba el nuevo",
        "descubrir que un compañero nuevo gana más que tú",
        ["salario", "transparenciasalarial", "negociacion"],
        """Llevaba cuatro años en la empresa cuando llegó un compañero nuevo, Felipe. Era amable y trabajador, pero tenía mucha menos experiencia que yo. Un viernes, en el almuerzo, hablando de mudanzas, soltó sin darse cuenta: «Mi sueldo apenas me alcanza para el apartamento nuevo, y eso que gano cuatro mil». Yo casi me atraganto. Yo ganaba tres mil doscientos. Después de cuatro años, más experiencia y mejor desempeño, ganaba ochocientos dólares menos que alguien que llevaba dos semanas. Sonreí y cambié de tema. Pero por dentro, algo hervía. Esa noche no pude dormir. Pensé en ir a gritarle al gerente. Pensé en renunciar al día siguiente. Pero me obligué a respirar. Si reaccionaba con rabia, iba a perder fuerza. Necesitaba una estrategia. Abrí una hoja en blanco y empecé a escribir todos mis logros de los cuatro años. Cuando terminé, la lista tenía treinta y dos líneas. Y entonces entendí lo que tenía que hacer.""",
        """El lunes pedí una reunión con mi gerente. No mencioné a Felipe, ni su sueldo, ni nada personal. Llevé mi lista de logros y una investigación de cuánto se paga en el mercado por mi puesto. «Quiero que revisemos mi salario», le dije. «Este es mi aporte y este es el rango del mercado». Mi gerente leyó las treinta y dos líneas en silencio. Me contestó lo de siempre: el presupuesto estaba ajustado, tal vez en seis meses. Yo había previsto esa respuesta. «Entiendo», le dije. «Pero tengo dos entrevistas la próxima semana en otras empresas, y prefiero quedarme aquí si podemos llegar a un acuerdo justo». Su expresión cambió. Pidió tres días. Al tercer día me llamó: subida a cuatro mil trescientos, con efecto inmediato. Más de lo que ganaba Felipe. Nunca le dije nada a él, no era su culpa. Pero aprendí que el sueldo no sube solo por trabajar bien. Sube cuando alguien se atreve a pedirlo con números en la mano.""",
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
        print(
            f"{path.name}: {title} ({len(part1.split())} + {len(part2.split())} palabras) #{' #'.join(tags)}"
        )
