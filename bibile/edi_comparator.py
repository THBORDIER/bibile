#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bibile - Comparaison EDI vs PDF

Rapproche les shipments EDI parses (depuis XML SourceCNX) avec les
enlevements extraits du PDF pour detecter les ecarts.

Matching par nom de societe (normalise en majuscules sans accents).
"""

import unicodedata


def _normalize(name):
    """Normalise un nom pour le matching : majuscules, sans accents, sans ponctuation."""
    if not name:
        return ''
    # Supprimer les accents
    nfkd = unicodedata.normalize('NFKD', str(name))
    sans_accents = ''.join(c for c in nfkd if not unicodedata.combining(c))
    # Majuscules, garder alphanumerique + espaces
    return ' '.join(sans_accents.upper().split())


def compare_edi_pdf(edi_shipments, pdf_enlevements):
    """Compare les shipments EDI parses avec les enlevements PDF.

    Le matching se fait par nom de societe normalise (sans accents, majuscules).

    Args:
        edi_shipments: list[dict] depuis fetch_edi_parsed()
        pdf_enlevements: list[dict] depuis la table enlevements SQLite

    Returns:
        dict avec matches, pdf_only, edi_only, stats
    """
    # Indexer les EDI par sold_by normalise
    edi_by_name = {}
    for s in edi_shipments:
        key = _normalize(s.get('sold_by', ''))
        if key:
            if key not in edi_by_name:
                edi_by_name[key] = []
            edi_by_name[key].append(s)

    matches = []
    pdf_only = []
    matched_edi_ids = set()

    for enl in pdf_enlevements:
        societe = enl.get('societe', '')
        num = enl.get('num_enlevement', '')
        key = _normalize(societe)
        if not key:
            continue

        # Chercher une correspondance exacte par nom
        edi_list = edi_by_name.get(key, [])

        # Trouver le meilleur match non encore utilise
        edi = None
        for candidate in edi_list:
            cid = id(candidate)
            if cid not in matched_edi_ids:
                edi = candidate
                matched_edi_ids.add(cid)
                break

        if edi:
            ecarts = []
            pdf_colis = enl.get('nb_colis', 0) or 0
            edi_colis = edi.get('total_colis', 0) or 0
            if pdf_colis != edi_colis:
                ecarts.append({'champ': 'colis', 'pdf': pdf_colis, 'edi': edi_colis})

            pdf_poids = float(enl.get('poids_total', 0) or 0)
            edi_poids = float(edi.get('poids_total', 0) or 0)
            if abs(pdf_poids - edi_poids) > 0.5:
                ecarts.append({'champ': 'poids', 'pdf': pdf_poids, 'edi': edi_poids})

            pdf_pal = enl.get('nb_palettes', 0) or 0
            edi_pal = edi.get('total_palettes', 0) or 0
            if pdf_pal != edi_pal:
                ecarts.append({'champ': 'palettes', 'pdf': pdf_pal, 'edi': edi_pal})

            matches.append({
                'num_enlevement': num,
                'societe': societe,
                'edi_societe': edi.get('sold_by', ''),
                'shipment_id': edi.get('shipment_id', ''),
                'pdf': {
                    'nb_palettes': pdf_pal,
                    'poids_total': pdf_poids,
                    'nb_colis': pdf_colis,
                },
                'edi': {
                    'total_palettes': edi_pal,
                    'total_poids': edi_poids,
                    'total_colis': edi_colis,
                },
                'ecarts': ecarts,
                'ok': len(ecarts) == 0,
            })
        else:
            pdf_only.append({
                'num_enlevement': num,
                'societe': societe,
                'nb_palettes': enl.get('nb_palettes', 0),
                'poids_total': enl.get('poids_total', 0),
                'nb_colis': enl.get('nb_colis', 0),
            })

    # EDI sans correspondance PDF
    edi_only = []
    for s in edi_shipments:
        if id(s) not in matched_edi_ids:
            edi_only.append({
                'shipment_id': s.get('shipment_id', ''),
                'transaction_ref': s.get('transaction_ref', ''),
                'sold_by': s.get('sold_by', ''),
                'total_colis': s.get('total_colis', 0),
                'total_poids': s.get('poids_total', 0),
                'total_palettes': s.get('total_palettes', 0),
                'date_trans': s.get('date_trans', ''),
            })

    nb_ecarts = sum(1 for m in matches if not m['ok'])
    stats = {
        'total_pdf': len(pdf_enlevements),
        'total_edi': len(edi_shipments),
        'matched': len(matches),
        'ecarts': nb_ecarts,
        'pdf_only': len(pdf_only),
        'edi_only': len(edi_only),
    }

    return {
        'matches': matches,
        'pdf_only': pdf_only,
        'edi_only': edi_only,
        'stats': stats,
    }
