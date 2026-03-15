#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bibile - Comparaison EDI vs PDF

Rapproche les shipments EDI parses (depuis XML SourceCNX) avec les
enlevements extraits du PDF pour detecter les ecarts.

1. Agregation des lignes PDF (1 ligne par palette → 1 ligne par enlevement)
2. Matching multi-criteres avec scoring (nom fuzzy + ville + poids + reference)
"""

import unicodedata
import difflib
from collections import defaultdict


def _normalize(name):
    """Normalise un nom : majuscules, sans accents, alphanum + espaces."""
    if not name:
        return ''
    nfkd = unicodedata.normalize('NFKD', str(name))
    sans_accents = ''.join(c for c in nfkd if not unicodedata.combining(c))
    cleaned = ''.join(c if c.isalnum() or c == ' ' else ' ' for c in sans_accents)
    return ' '.join(cleaned.upper().split())


def _aggregate_pdf(pdf_rows):
    """Agrege les lignes PDF par enlevement (1 ligne par palette → 1 par enlevement).

    Groupe par (extraction_id, num_enlevement), somme poids/colis/palettes.
    """
    groups = defaultdict(list)
    for r in pdf_rows:
        key = (r.get('extraction_id'), r.get('num_enlevement'))
        groups[key].append(r)

    aggregated = []
    for (ext_id, num), rows in groups.items():
        first = rows[0]
        refs = [r.get('reference', '') for r in rows if r.get('reference')]
        aggregated.append({
            'extraction_id': ext_id,
            'num_enlevement': num,
            'societe': first.get('societe', ''),
            'ville': first.get('ville', ''),
            'reference': first.get('reference', ''),
            'references': refs,
            'nb_palettes': sum(float(r.get('nb_palettes', 0) or 0) for r in rows),
            'poids_total': sum(float(r.get('poids_total', 0) or 0) for r in rows),
            'nb_colis': sum(float(r.get('nb_colis', 0) or 0) for r in rows),
            'livraison': first.get('livraison', ''),
            'telephone': first.get('telephone', ''),
        })
    return aggregated


def _score_match(pdf_enl, edi_ship):
    """Calcule un score de correspondance (0-100) entre un enlevement PDF et un shipment EDI.

    Returns:
        (score, matched_by) — score total et liste des criteres qui ont matche
    """
    score = 0
    matched_by = []

    # 1. Nom societe (50 pts max) — fuzzy matching
    pdf_name = _normalize(pdf_enl.get('societe', ''))
    edi_name = _normalize(edi_ship.get('sold_by', ''))
    if pdf_name and edi_name:
        ratio = difflib.SequenceMatcher(None, pdf_name, edi_name).ratio()
        if ratio >= 0.6:
            name_score = int(ratio * 50)
            score += name_score
            matched_by.append('Nom')

    # 2. Ville (25 pts max)
    pdf_ville = _normalize(pdf_enl.get('ville', ''))
    edi_ville = _normalize(edi_ship.get('sold_by_city', ''))
    if pdf_ville and edi_ville:
        if pdf_ville == edi_ville:
            score += 25
            matched_by.append('Ville')
        else:
            ville_ratio = difflib.SequenceMatcher(None, pdf_ville, edi_ville).ratio()
            if ville_ratio >= 0.8:
                score += 15
                matched_by.append('Ville~')

    # 3. Poids (15 pts max) — proximite relative
    pdf_poids = float(pdf_enl.get('poids_total', 0) or 0)
    edi_poids = float(edi_ship.get('poids_total', 0) or 0)
    if pdf_poids > 0 and edi_poids > 0:
        ecart_pct = abs(pdf_poids - edi_poids) / max(pdf_poids, edi_poids)
        if ecart_pct <= 0.05:
            score += 15
            matched_by.append('Poids')
        elif ecart_pct <= 0.10:
            score += 10
            matched_by.append('Poids~')
        elif ecart_pct <= 0.20:
            score += 5

    # 4. Reference croisee (10 pts bonus)
    refs = pdf_enl.get('references', [])
    if not refs:
        ref = pdf_enl.get('reference', '')
        refs = [ref] if ref else []
    edi_ref = str(edi_ship.get('transaction_ref', '') or '').upper()
    edi_sid = str(edi_ship.get('shipment_id', '') or '').upper()
    for ref in refs:
        ref_up = ref.strip().upper()
        if ref_up and (ref_up in edi_ref or ref_up in edi_sid or edi_ref in ref_up or edi_sid in ref_up):
            score += 10
            matched_by.append('Ref')
            break

    return score, matched_by


def compare_edi_pdf(edi_shipments, pdf_enlevements):
    """Compare les shipments EDI avec les enlevements PDF.

    1. Agrege les lignes PDF par enlevement (1 palette = 1 ligne → 1 enlevement)
    2. Score multi-criteres pour chaque paire possible
    3. Greedy best-first matching (meilleurs scores d'abord)

    Returns:
        dict avec matches, pdf_only, edi_only, stats
    """
    # Agregation PDF
    pdf_agg = _aggregate_pdf(pdf_enlevements)

    # Calculer tous les scores
    all_scores = []
    for i, pdf in enumerate(pdf_agg):
        for j, edi in enumerate(edi_shipments):
            score, matched_by = _score_match(pdf, edi)
            if score >= 40:
                all_scores.append((score, matched_by, i, j))

    # Tri decroissant par score (greedy best-first)
    all_scores.sort(key=lambda x: -x[0])

    matches = []
    matched_pdf = set()
    matched_edi = set()

    for score, matched_by, i, j in all_scores:
        if i in matched_pdf or j in matched_edi:
            continue

        pdf = pdf_agg[i]
        edi = edi_shipments[j]
        matched_pdf.add(i)
        matched_edi.add(j)

        # Comparer les valeurs
        ecarts = []
        pdf_colis = float(pdf.get('nb_colis', 0) or 0)
        edi_colis = float(edi.get('total_colis', 0) or 0)
        if pdf_colis != edi_colis:
            ecarts.append({'champ': 'colis', 'pdf': pdf_colis, 'edi': edi_colis})

        pdf_poids = float(pdf.get('poids_total', 0) or 0)
        edi_poids = float(edi.get('poids_total', 0) or 0)
        if abs(pdf_poids - edi_poids) > 0.5:
            ecarts.append({'champ': 'poids', 'pdf': pdf_poids, 'edi': edi_poids})

        pdf_pal = float(pdf.get('nb_palettes', 0) or 0)
        edi_pal = float(edi.get('total_palettes', 0) or 0)
        if pdf_pal != edi_pal:
            ecarts.append({'champ': 'palettes', 'pdf': pdf_pal, 'edi': edi_pal})

        matches.append({
            'num_enlevement': pdf.get('num_enlevement', ''),
            'societe': pdf.get('societe', ''),
            'edi_societe': edi.get('sold_by', ''),
            'shipment_id': edi.get('shipment_id', ''),
            'score': score,
            'matched_by': ' + '.join(matched_by),
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

    # PDF sans correspondance
    pdf_only = []
    for i, pdf in enumerate(pdf_agg):
        if i not in matched_pdf:
            pdf_only.append({
                'num_enlevement': pdf.get('num_enlevement', ''),
                'societe': pdf.get('societe', ''),
                'nb_palettes': pdf.get('nb_palettes', 0),
                'poids_total': pdf.get('poids_total', 0),
                'nb_colis': pdf.get('nb_colis', 0),
            })

    # EDI sans correspondance
    edi_only = []
    for j, s in enumerate(edi_shipments):
        if j not in matched_edi:
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
    total_pdf = len(pdf_agg)
    stats = {
        'total_pdf': total_pdf,
        'total_edi': len(edi_shipments),
        'matched': len(matches),
        'ecarts': nb_ecarts,
        'pdf_only': len(pdf_only),
        'edi_only': len(edi_only),
        'match_pct': round(100 * len(matches) / total_pdf) if total_pdf > 0 else 0,
    }

    return {
        'matches': matches,
        'pdf_only': pdf_only,
        'edi_only': edi_only,
        'stats': stats,
    }
