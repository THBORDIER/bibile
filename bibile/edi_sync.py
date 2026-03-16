#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bibile - Module de synchronisation EDI avec BDD Drakkar (SQL Express)

Connexion a la BDD Drakkar pour recuperer les messages EDI du client
JF HILLEBRAND TRANSIT (alias HILL21BEAU) depuis la table edi_atlas400.
"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime

logger = logging.getLogger('bibile.edi')

# Client cible
CLIENT_ALIAS = 'HILL21BEAU'

# Flag global pyodbc
_using_pyodbc = False


def _get_drakkar_connection(config):
    """Cree une connexion a la BDD Drakkar (SQL Express local).

    Tente pyodbc en priorite, fallback pymssql.
    Pas de chiffrement Azure — TrustServerCertificate=yes.
    """
    global _using_pyodbc
    host = config['host']
    port = int(config.get('port', 49372))
    user = config['username']
    password = config.get('password_encrypted', '')
    database = config['database_name']

    # pyodbc
    try:
        import pyodbc
        drivers = pyodbc.drivers()
        odbc_driver = None
        for preferred in ['ODBC Driver 18 for SQL Server', 'ODBC Driver 17 for SQL Server']:
            if preferred in drivers:
                odbc_driver = preferred
                break

        if odbc_driver:
            conn_str = (
                f"DRIVER={{{odbc_driver}}};"
                f"SERVER={host},{port};"
                f"DATABASE={database};"
                f"UID={user};"
                f"PWD={password};"
                f"TrustServerCertificate=yes;"
                f"Connection Timeout=15;"
            )
            conn = pyodbc.connect(conn_str)
            conn.timeout = 30
            _using_pyodbc = True
            return conn
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"pyodbc echoue, fallback pymssql: {e}")

    # Fallback pymssql
    import pymssql
    _using_pyodbc = False
    return pymssql.connect(
        server=host,
        port=port,
        user=user,
        password=password,
        database=database,
        login_timeout=15,
        timeout=30,
        as_dict=True,
    )


def _sql(query):
    """Convertit %s en ? si pyodbc."""
    if _using_pyodbc:
        return query.replace('%s', '?')
    return query


def _row_to_dict(cursor, row):
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))


def _fetchall_dict(cursor):
    rows = cursor.fetchall()
    if not rows:
        return []
    if isinstance(rows[0], dict):
        return rows
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def test_drakkar_connection(config):
    """Teste la connexion a Drakkar. Retourne (success, message)."""
    try:
        conn = _get_drakkar_connection(config)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()

        # Compter les messages EDI pour le client
        cursor.execute(_sql("""
            SELECT COUNT(*) AS cnt
            FROM [dbo].[edi_atlas400] e
            LEFT JOIN [dbo].[ti] t ON e.Code_Indus = t.N_tiers
            WHERE t.Alias_tiers = %s
        """), (CLIENT_ALIAS,))
        row = _row_to_dict(cursor, cursor.fetchone())
        cnt = row.get('cnt', 0) if row else 0

        driver_name = 'pyodbc' if _using_pyodbc else 'pymssql'
        conn.close()
        return True, f"Connecte via {driver_name} - {cnt} messages EDI trouves"
    except Exception as e:
        return False, f"Erreur connexion Drakkar: {e}"


def fetch_edi_messages(config, date_from=None, date_to=None):
    """Recupere les messages EDI du client HILLEBRAND pour une periode.

    Args:
        config: dict de connexion
        date_from: str 'YYYY-MM-DD' (inclus)
        date_to: str 'YYYY-MM-DD' (inclus)

    Returns:
        list[dict] avec les champs normalises
    """
    conn = _get_drakkar_connection(config)
    cursor = conn.cursor()

    query = """
        SELECT
            e.Id_Ligne, e.Code_Indus, e.Sens, e.Date_Trans, e.Fich_Suiv,
            e.RefMessage, e.IdentMessage, e.TotalColis, e.TotalPoids, e.TotalPositions,
            CAST(e.SourceCNX AS NVARCHAR(MAX)) AS SourceCNX
        FROM [dbo].[edi_atlas400] e
        LEFT JOIN [dbo].[ti] t ON e.Code_Indus = t.N_tiers
        WHERE t.Alias_tiers = %s
    """
    params = [CLIENT_ALIAS]

    if date_from:
        query += " AND e.Date_Trans >= CONVERT(datetime, %s, 120)"
        params.append(date_from + ' 00:00:00')
    if date_to:
        query += " AND e.Date_Trans < CONVERT(datetime, %s, 120)"
        params.append(date_to + ' 23:59:59')

    query += " ORDER BY e.Date_Trans DESC"

    cursor.execute(_sql(query), tuple(params))
    rows = _fetchall_dict(cursor)
    conn.close()

    # Normaliser les dates
    results = []
    for r in rows:
        dt = r.get('Date_Trans')
        if dt and isinstance(dt, datetime):
            r['Date_Trans'] = dt.isoformat()
        results.append(r)

    return results


def fetch_edi_stats(config, date_from=None, date_to=None):
    """Statistiques agregees des messages EDI du client."""
    conn = _get_drakkar_connection(config)
    cursor = conn.cursor()

    query = """
        SELECT
            COUNT(*) AS total_messages,
            MIN(e.Date_Trans) AS first_date,
            MAX(e.Date_Trans) AS last_date,
            SUM(COALESCE(e.TotalColis, 0)) AS total_colis,
            SUM(COALESCE(e.TotalPoids, 0)) AS total_poids,
            SUM(COALESCE(e.TotalPositions, 0)) AS total_positions
        FROM [dbo].[edi_atlas400] e
        LEFT JOIN [dbo].[ti] t ON e.Code_Indus = t.N_tiers
        WHERE t.Alias_tiers = %s
    """
    params = [CLIENT_ALIAS]

    if date_from:
        query += " AND e.Date_Trans >= CONVERT(datetime, %s, 120)"
        params.append(date_from + ' 00:00:00')
    if date_to:
        query += " AND e.Date_Trans < CONVERT(datetime, %s, 120)"
        params.append(date_to + ' 23:59:59')

    cursor.execute(_sql(query), tuple(params))
    row = _row_to_dict(cursor, cursor.fetchone())
    conn.close()

    if not row:
        return {'total_messages': 0}

    # Normaliser les dates
    for key in ('first_date', 'last_date'):
        val = row.get(key)
        if val and isinstance(val, datetime):
            row[key] = val.isoformat()

    return row


# ===== PARSER XML SourceCNX =====

# Namespace Hillebrand
_NS = {'h': 'http://JFH.Interfaces2013.Schemas.Schemas.HillebrandTransportInstructionsMessage_2.0'}


def _fix_encoding(text):
    """Corrige le double-encodage UTF-8 sur une chaine individuelle.

    pyodbc peut decoder NTEXT comme latin-1, produisant 'FranÃ§ois' au lieu de 'François'.
    """
    if not text:
        return text
    try:
        fixed = text.encode('latin-1').decode('utf-8')
        return fixed
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text


def _find_text(elem, path, ns=None):
    """Trouve le texte d'un sous-element, retourne '' si absent."""
    child = elem.find(path, ns or _NS)
    if child is not None and child.text:
        return _fix_encoding(child.text.strip())
    return ''


def parse_source_cnx(source_cnx_text):
    """Parse le XML SourceCNX et extrait les shipments.

    Returns:
        list[dict] avec un dict par shipment contenant:
        - shipment_id, transaction_ref, sold_by, sold_by_city
        - total_colis, total_palettes, type_palettes, poids_total
        - pickup_date, delivery_city, instructions
    """
    if not source_cnx_text:
        return []

    try:
        # Corriger le double-encodage UTF-8 (pyodbc decode NTEXT comme latin-1)
        xml_text = source_cnx_text
        try:
            xml_text = xml_text.encode('latin-1').decode('utf-8')
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass  # Deja correctement encode
        start = xml_text.find('<HillebrandTransportInstructionsRoot')
        end = xml_text.find('</EDI_ATLAS>')
        if start >= 0 and end > start:
            xml_text = xml_text[start:end]

        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.warning(f"Erreur parsing XML EDI: {e}")
        return []

    results = []

    # Transaction reference depuis Header
    transaction_ref = _find_text(root, './/h:Header/h:TransactionReference')

    # Instructions globales
    instructions = _find_text(root, './/h:Body/h:Instructions')

    # Pickup date depuis Transport locations
    pickup_date = ''
    for loc in root.findall('.//h:TransportLocation', _NS):
        loc_type = _find_text(loc, 'h:TransportLocationType')
        if loc_type == 'Goods loading':
            pickup_date = _find_text(loc, './/h:EarliestPickUpDateTime/h:Date')
            break

    # Delivery info depuis Transport locations
    delivery_city = ''
    delivery_name = ''
    for loc in root.findall('.//h:TransportLocation', _NS):
        loc_type = _find_text(loc, 'h:TransportLocationType')
        if loc_type == 'Goods unloading':
            delivery_city = _find_text(loc, './/h:TransportLocationAddress/h:AddressInfo/h:CityName')
            delivery_name = _find_text(loc, './/h:TransportLocationAddress/h:Name')
            break

    # Shipments
    for shipment in root.findall('.//h:Shipment', _NS):
        sid = _find_text(shipment, 'h:HillebrandShipmentID')

        # Expediteur (SoldBy)
        sold_by = _find_text(shipment, './/h:SoldBy/h:Name')
        sold_by_city = _find_text(shipment, './/h:SoldBy/h:AddressInfo/h:CityName')

        # Colis
        total_colis = _find_text(shipment, './/h:TotalPackages/h:TotalPackages/h:Quantity')

        # Palettes
        total_palettes = _find_text(shipment, 'h:TotalPallets')
        type_palettes = _find_text(shipment, './/h:Pallets/h:Pallet/h:PalletType')

        # Poids
        poids = _find_text(shipment, './/h:TotalGrossWeight/h:Weight')

        results.append({
            'shipment_id': sid,
            'transaction_ref': transaction_ref,
            'sold_by': sold_by,
            'sold_by_city': sold_by_city,
            'total_colis': int(total_colis) if total_colis else 0,
            'total_palettes': int(total_palettes) if total_palettes else 0,
            'type_palettes': type_palettes,
            'poids_total': float(poids) if poids else 0.0,
            'pickup_date': pickup_date,
            'delivery_city': delivery_city,
            'delivery_name': delivery_name,
            'instructions': instructions,
        })

    return results


def fetch_edi_parsed(config, date_from=None, date_to=None):
    """Recupere et parse les EDI — retourne les shipments extraits du XML.

    Les messages sont tries par Date_Trans DESC, donc le plus recent est traite
    en premier. Si un meme shipment_id apparait dans plusieurs messages (MAJ
    dans la journee), seul le plus recent est conserve.

    Returns:
        list[dict] un dict par shipment avec les infos parsees
    """
    messages = fetch_edi_messages(config, date_from=date_from, date_to=date_to)
    seen_shipments = {}

    for msg in messages:
        source = msg.get('SourceCNX', '')
        if not source:
            continue
        shipments = parse_source_cnx(source)
        for s in shipments:
            s['edi_id'] = msg.get('Id_Ligne')
            s['date_trans'] = msg.get('Date_Trans', '')
            s['fich_suiv'] = msg.get('Fich_Suiv', '')
            sid = s.get('shipment_id', '')
            if sid and sid not in seen_shipments:
                seen_shipments[sid] = s
            elif not sid:
                seen_shipments[f'_no_id_{msg.get("Id_Ligne")}'] = s

    return list(seen_shipments.values())
