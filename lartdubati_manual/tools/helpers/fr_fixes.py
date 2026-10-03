# (file, old, new) — libellés alignés sur l'interface Odoo 18 (fichiers de traduction officiels fr.po)
FIXES = [
 ("Chantier.md", "**Maintenance → Équipements**", "**Maintenance → Équipement**"),
 ("Comptable.md", "**Maintenance → Équipements**", "**Maintenance → Équipement**"),
 ("Responsable parc.md", "**Maintenance → Équipements**", "**Maintenance → Équipement**"),
 ("Référence.md", "**Maintenance → Équipements**", "**Maintenance → Équipement**"),
 ("Comptable.md", "Onglet **Informations produit**", "Onglet **Informations sur le produit**"),
 ("Responsable parc.md", "Onglet **Informations produit**", "Onglet **Informations sur le produit**"),
 ("Référence.md", "l'onglet Informations produit", "l'onglet Informations sur le produit"),
 ("Référence.md", "| Informations produit (natif) | Fournisseur, Modèle, Numéro de série, Garantie |", "| Informations sur le produit (natif) | Fournisseur, Modèle, Numéro de série, Date d'expiration de garantie |"),
 ("Référence.md", "| Informations produit (natif) | Coût |", "| Informations sur le produit (natif) | Coût |"),
 ("Référence.md", "« Utilisé à l'emplacement »", "« Lieu d'utilisation »"),
 ("Responsable parc.md", "« Utilisé à l'emplacement »", "« Lieu d'utilisation »"),
 ("Responsable parc.md", "Décocher **Peut être vendu**, laisser **Peut être acheté**. Type = Service ; Bien stockable seulement si on veut aussi compter des pièces de ce modèle en stock.",
  "Décocher **Ventes**, laisser **Achat** coché. **Type de produit** = Service ; seulement si on veut aussi compter des pièces de ce modèle en stock : Biens, avec **Suivre l'inventaire** coché."),
 ("Responsable parc.md", "cocher Partager avec tous les utilisateurs", "cocher **Partagé**"),
 ("Admin Odoo.md", "Section **Valorisation de l'inventaire**", "Section **Valorisation d'inventaire**"),
 ("Admin Odoo.md", "Section **Propriétés de compte**", "Section **Propriétés du compte**"),
 ("Admin Odoo.md", "Onglet **Contacts et adresses** → Ajouter un contact", "Onglet **Contacts & Adresses** → Ajouter"),
 ("Comptable.md", "Comptabilité → Configuration → Comptabilité → Plan comptable → Nouveau", "**Facturation → Configuration → Comptabilité → Plan comptable → Nouveau**"),
 ("Comptable.md", "Peut être acheté : coché — Peut être vendu : décoché", "Achat : coché — Ventes : décoché"),
 ("Comptable.md", "(Achats → Factures fournisseurs → Nouvelle)", "(**Facturation → Fournisseurs → Factures fournisseurs → Nouveau**)"),
 ("Comptable.md", "**Vérification** : le compte de résultat (Comptabilité → Rapports) affiche les montants sous le bon compte.",
  "**Vérification** : dans **Facturation → Comptabilité → Écritures comptables**, un filtre sur le compte affiche les montants sous le bon compte."),
]
if __name__ == "__main__":
    import sys
    d = sys.argv[1]
    for f, o, n in FIXES:
        p = f"{d}/{f}"; t = open(p, encoding="utf-8").read()
        c = t.count(o)
        if c == 0: print("NOT FOUND", f, o[:50]); continue
        open(p, "w", encoding="utf-8").write(t.replace(o, n)); print(c, f, o[:50])
