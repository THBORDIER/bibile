#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bibile - Comparaison EDI vs PDF

Rapproche les messages EDI (Drakkar) avec les enlevements extraits du PDF
pour detecter les ecarts (colis, poids, enlevements manquants).
"""


def compare_edi_pdf(edi_messages, pdf_enlevements):
    """Compare les messages EDI avec les enlevements PDF.

    Args:
        edi_messages: list[dict] depuis fetch_edi_messages()
            Champs utilises: RefMessage, TotalColis, TotalPoids, TotalPositions
        pdf_enlevements: list[dict] depuis la table enlevements SQLite
            Champs utilises: num_enlevement, societe, nb_palettes, poids_total, nb_colis

    Returns:
        dict avec matches, pdf_only, edi_only, stats
    """
    # Indexer les EDI par RefMessage (numero d'enlevement)
    edi_by_ref = {}
    for edi in edi_messages:
        ref = str(edi.get('RefMessage', '')).strip()
        if ref:
            edi_by_ref[ref] = edi

    matches = []
    pdf_only = []
    matched_refs = set()

    for enl in pdf_enlevements:
        num = str(enl.get('num_enlevement', '')).strip()
        if not num:
            continue

        edi = edi_by_ref.get(num)
        if edi:
            matched_refs.add(num)
            # Comparer les valeurs
            ecarts = []
            pdf_colis = enl.get('nb_colis', 0) or 0
            edi_colis = edi.get('TotalColis', 0) or 0
            if pdf_colis != edi_colis:
                ecarts.append({'champ': 'colis', 'pdf': pdf_colis, 'edi': edi_colis})

            pdf_poids = enl.get('poids_total', 0) or 0
            edi_poids = edi.get('TotalPoids', 0) or 0
            if abs(pdf_poids - edi_poids) > 0.5:
                ecarts.append({'champ': 'poids', 'pdf': pdf_poids, 'edi': edi_poids})

            pdf_pal = enl.get('nb_palettes', 0) or 0
            edi_pos = edi.get('TotalPositions', 0) or 0
            if pdf_pal != edi_pos:
                ecarts.append({'champ': 'palettes', 'pdf': pdf_pal, 'edi': edi_pos})

            matches.append({
                'num_enlevement': num,
                'societe': enl.get('societe', ''),
                'pdf': {
                    'nb_palettes': pdf_pal,
                    'poids_total': pdf_poids,
                    'nb_colis': pdf_colis,
                },
                'edi': {
                    'total_positions': edi_pos,
                    'total_poids': edi_poids,
                    'total_colis': edi_colis,
                },
                'ecarts': ecarts,
                'ok': len(ecarts) == 0,
            })
        else:
            pdf_only.append({
                'num_enlevement': num,
                'societe': enl.get('societe', ''),
                'nb_palettes': enl.get('nb_palettes', 0),
                'poids_total': enl.get('poids_total', 0),
                'nb_colis': enl.get('nb_colis', 0),
            })

    # EDI sans correspondance PDF
    edi_only = []
    for ref, edi in edi_by_ref.items():
        if ref not in matched_refs:
            edi_only.append({
                'ref_message': ref,
                'total_colis': edi.get('TotalColis', 0),
                'total_poids': edi.get('TotalPoids', 0),
                'total_positions': edi.get('TotalPositions', 0),
                'date_trans': edi.get('Date_Trans', ''),
            })

    nb_ecarts = sum(1 for m in matches if not m['ok'])
    stats = {
        'total_pdf': len(pdf_enlevements),
        'total_edi': len(edi_messages),
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
