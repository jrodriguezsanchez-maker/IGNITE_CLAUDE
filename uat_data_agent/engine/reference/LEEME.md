Código usado en el análisis del 06-nov-2026 (chat). Funciona, pero tiene rutas fijas (/mnt/user-data/..., /home/claude/work).
- parse.py: lector del campo Data (normaliza etiquetas: Plant/Sup. Plant/C.Code/P.Org/S.Org/Doc Type/Material...).
- checks.py + engine.py: checks D01–M01 contra Org.Structure (ver Excel de análisis, hoja 00_Leeme).
- profile.py: perfil de dato por caso a partir de transacciones.
- patch.py: escritura no destructiva de AG–AL (solo sheet2.xml y table2.xml). Verificado: A:AF idénticas en 7.396 filas.
- v0_values.py: valores de la v0 (exclusividad de material por caso).
Reutilizar quitando rutas fijas; no reescribir desde cero.
