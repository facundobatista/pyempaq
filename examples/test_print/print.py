def check_respuesta(respuesta):
    if respuesta == "1":
        print("Perfecto.")
    else:
        print("Valor seleccionado incorrecto.")


print("""
Esto se imprime.
En este momento deberíamos ver el texto del input con la frase
"Elija el número 1: " pero lo vemos sólo luego de ingresar el valor.
""")

rta = input("Elija el número 1: ")
print()
check_respuesta(rta)
