Contexto: este proyecto genera datos de prueba dedicados por caso para el fichero UAT de iGnite SCM HUMAN. Lee SAP UAT en solo lectura por SAP GUI Scripting y escribe la propuesta en las columnas AG–AL de una copia del fichero.

Antes de nada lee CLAUDE.md, README.md, config/settings.yaml, config/rules.yaml, config/extractions.yaml, sap/ y engine/reference/ (incluido LEEME.md). Comprueba que en data/project/ está el fichero UAT y que la hoja "UAT_testscript - breaks by unit" tiene Table1 en A1:AF7080.

En esta primera sesión NO escribas código, NO modifiques ficheros y NO ejecutes nada contra SAP. Solo quiero:
1. Lo que has entendido (objetivo, reglas no negociables, flujos y tablas) en 10 líneas como máximo.
2. Contradicciones o huecos entre CLAUDE.md, los YAML y el código de referencia.
3. Un plan por fases, con entregable y forma de verificarlo en cada una:
   - engine/readers.py: leer exportaciones SE16N (texto con tabuladores) y CSV/XLSX manuales; validar output_fields de extractions.yaml y fallar con mensaje claro si falta una columna.
   - engine/compose.py: detectar el flujo de cada caso (ZTRA, ZINT/ZINR, ZPO, ZSPO, ZSPA, venta, PP, QM, PM, WM, transporte); elegir candidatos con rules.yaml, modelo dedicado y registro de reservas data/ledger/reservas.csv; generar AG–AL y out/peticion_creacion_maestros.csv.
   - engine/patch_xlsx.py: a partir de engine/reference/patch.py, sin rutas fijas.
   - tests/: extracciones simuladas en tests/mock para probar todo sin SAP.
4. Las preguntas que necesitas que yo responda, empezando por los pendientes de rules.yaml y extractions.yaml (fecha "desde", clases de venta, ZSER, ZPAS, ZINT/ZTRA, BP dedicado).

Responde en español.
