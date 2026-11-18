"""Valida la lectura de MB52 contra una captura del usuario (verdad conocida): centro M117, almacén 1000.
SOLO LECTURA. Lee el listado completo del centro/almacén con el mismo código que usa el chequeo y compara material, lote y cantidad
con las líneas visibles en la captura. Además repite la lectura incluyendo stocks especiales para ver si hay stock que el chequeo no cuenta.
Salvar la salida a un fichero; no cortarla con tuberías."""
import faulthandler
import sys

import sap_backend
import sap_mb52

faulthandler.dump_traceback_later(280, exit=True)

CENTRO, ALMACEN = "M117", "1000"
# (material, lote, cantidad libre) tal como se ven en la captura del usuario
ESPERADO = [
    ("102259", "1339100", 3000), ("102259", "1464492", 17000),
    ("107553", "0000000110", 10000), ("107553", "08/2026", 25003), ("107553", "26AOUT2026", 16000), ("107553", "LOT23AOUT", 1000),
    ("107555", "DOC0052621", 2000), ("107556", "25082601", 800),
    ("301128", "9999", 330), ("304629", "9999", 950),
    ("316763", "25000411", 102820), ("316763", "6350781482", 106000), ("316763", "6350832144", 413662.1), ("316763", "6350856358", 1027600),
    ("316764", "6350856361", 267650.47), ("316765", "6350808099", 126128.08), ("316765", "6350832146", 98000),
    ("316812", "07MAR2026", 17), ("316812", "27750501", 2700),
    ("318043", "LOT:260316", 62000),
    ("318044", "29AVR26", 3827), ("318044", "LAIZ195MM", 318), ("318044", "LAIZ250MM", 1096), ("318044", "LAIZ325MM", 434), ("318044", "LAIZ330MM", 1042),
    ("318608", "LOT13FILM", 2200),
    ("320237", "138/2026", 4000), ("320237", "140/2026", 21500), ("320237", "LOT N°231", 183000), ("320237", "LOTN°231", 788050),
    ("320237", "N°231", 32000), ("320237", "N°309", 379000),
    ("320238", "391/2025", 750),
]


def leer(ses, especiales):
    r = sap_mb52.consultar(ses, "", CENTRO, ALMACEN, lotes=True, especiales=especiales, max_filas=5000)
    filas = {}
    n_datos = 0
    for f in r["filas"]:
        mat = str(f.get("MATNR", "")).strip()
        if not mat:
            continue                                     # fila de totales
        n_datos += 1
        filas[(mat.lstrip("0"), str(f.get("CHARG", "")).strip())] = filas.get((mat.lstrip("0"), str(f.get("CHARG", "")).strip()), 0.0) + sap_backend.numero(f.get("LABST", "0"))
    return r, filas, n_datos


def main():
    p = (sap_backend.leer_config().get("sistemas_permitidos") or [None])[0]
    pc = sap_mb52.pythoncom
    pc.CoInitialize()
    ses = creada = None
    try:
        ses, creada = sap_mb52.sesion(p["sid"], crear=True, mandante=p["mandante"], conexion=p.get("conexion"))
        assert str(ses.Info.SystemName).upper() == p["sid"].upper() and str(ses.Info.Client) == str(p["mandante"])
        r, filas, n = leer(ses, False)
        print("MB52 %s/%s (sin stocks especiales): %d líneas con material · total filas del ALV %s · mensaje %r" % (CENTRO, ALMACEN, n, r.get("total_filas"), r["mensaje"]), flush=True)
        ok = mal = falta = 0
        for mat, lote, cant in ESPERADO:
            v = filas.get((mat, lote))
            if v is None:
                falta += 1
                print("  FALTA     %s lote %-12s esperado %s" % (mat, lote.encode("ascii", "replace").decode(), cant), flush=True)
            elif abs(v - cant) > 1e-6 * max(1, cant):
                mal += 1
                print("  DISTINTO  %s lote %-12s esperado %s · leído %s" % (mat, lote.encode("ascii", "replace").decode(), cant, v), flush=True)
            else:
                ok += 1
        print("RESULTADO: %d de %d coinciden · %d con cantidad distinta · %d no encontradas" % (ok, len(ESPERADO), mal, falta), flush=True)
        r2, filas2, n2 = leer(ses, True)
        extra = n2 - n
        print("\nCon stocks especiales incluidos: %d líneas (%+d respecto a sin ellos)" % (n2, extra), flush=True)
        if extra:
            nuevas = [k for k in filas2 if k not in filas][:8]
            print("  ejemplos de líneas que el chequeo NO ve por ser stock especial:", [(m, l.encode('ascii', 'replace').decode(), filas2[(m, l)]) for m, l in nuevas], flush=True)
        print("transacción final:", ses.Info.Transaction, flush=True)
    finally:
        if ses is not None and creada:
            sap_mb52.cerrar_sesion(ses)
            print("sesión nueva cerrada.", flush=True)
        pc.CoUninitialize()


if __name__ == "__main__":
    sys.exit(main())
