# sqorus-veille-donnees

Relais de données publiques ouvertes pour la veille de la plateforme SQORUS Bid Intelligence.

Deux fois par jour, GitHub Actions télécharge :
- **APProch** — projets d'achats publics de l'État (data.economie.gouv.fr, licence ouverte) ;
- **DECP consolidées** — données essentielles des marchés publics attribués (data.gouv.fr, licence ouverte) ;

garde les lignes qui contiennent les mots-clés de `relais/mots-cles.json`, et publie le résultat dans `donnees/`.
Le service de Claude de la plateforme lit ces fichiers ; il ne peut pas joindre ces deux sites directement.

- Aucune clé ni donnée confidentielle : uniquement des données publiques.
- `donnees/statut.json` donne l'état de chaque source (ok, ou échec avec l'erreur exacte).
- Lancement manuel : onglet **Actions** › « Relais de veille » › **Run workflow**.
