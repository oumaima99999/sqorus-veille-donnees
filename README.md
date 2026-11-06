# Branche relais-documents

Relais de téléchargement du module « Chances de gain » (SQORUS Bid Intelligence) : le relais dépose une demande dans
`demandes/<id>.json`, GitHub Actions télécharge les documents publics demandés et publie leur texte intégral, page par
page, dans `textes/<id>.json`. Branche séparée : la veille (`main`) n'est pas concernée.
