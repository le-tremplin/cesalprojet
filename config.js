/*
 * Configuration du site : c'est le SEUL fichier à modifier en cas de changement d'adresse.
 *
 * 1. Changer URL_BASE ci-dessous (avec la barre oblique finale).
 * 2. Régénérer le QR code :  python3 outils/generer_qr.py
 *    (le script relit URL_BASE dans ce fichier).
 * 3. Réimprimer le QR : l'ancien pointe vers l'ancienne adresse.
 */
window.CONFIG = {
  URL_BASE: "https://ylieselamri-bot.github.io/cesalprojet/",

  NOM: "Le Tremplin",
  SOUS_TITRE: "ancien CESAL, Bourges",
  MENTION: "Document d'étude – BUT GCCD – ne remplace pas le plan d'intervention officiel",

  /*
   * Mot de passe simple, DÉSACTIVÉ par défaut.
   * Limite : sur un site statique (GitHub Pages), il masque seulement l'affichage.
   * Les fichiers (plans, données) restent téléchargeables par qui connaît leur adresse.
   * Pour l'activer : actif: true, et mettre dans sha256 l'empreinte SHA-256 du mot de passe
   * (par ex. : printf 'monmotdepasse' | sha256sum).
   */
  MOT_DE_PASSE: {
    actif: false,
    sha256: ""
  }
};
