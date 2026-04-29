import discord

# ══════════════════════════════════════════════
#  COSTANTI — RDR2 RP BOT
# ══════════════════════════════════════════════

STAFF_ROLE_ID     = 1404051875426467902
SCERIFFO_ROLE_ID  = 1404051916140449885
DOTTORE_ROLE_ID   = 1420996354951479346
ARMIERE_ROLE_ID   = 1404051953188733002
STALLA_ROLE_ID    = 1404051942698913792
SALOON_ROLE_ID    = 1404051995152617576
EMPORIO_ROLE_ID   = 1404051971102740490
CONTRABBANDO_ID   = 1404052032100368455
STATO_ROLE_ID     = 1404051912197931109
DILIGENZA_ROLE_ID = [1421007310771191829, 1421007929301139626]
CHIAVE_ROLE_ID    = 1404051860121456701
BANKER_ROLE_ID    = 1404051937438994493
DISTILL_ROLE_ID   = 1421167674813317120
MACELLERIA_ROLE_ID= 1421000310951772251
FIGHT_ROLE_ID     = 1421169805968539699

LOG_CHANNEL_ID    = 1479158931610931414
BANK_CHANNEL_ID   = 1404052325609504798
DATABASE_NAME     = "rdr2_bot.db"

# Gruppi
STAFF_ROLES    = [STAFF_ROLE_ID, CHIAVE_ROLE_ID]
SCERIFFO_ROLES = [SCERIFFO_ROLE_ID, STATO_ROLE_ID]

COMPANY_ROLES = {
    "Sceriffo":     SCERIFFO_ROLE_ID,
    "Dottore":      DOTTORE_ROLE_ID,
    "Armiere":      ARMIERE_ROLE_ID,
    "Stalla":       STALLA_ROLE_ID,
    "Saloon":       SALOON_ROLE_ID,
    "Emporio":      EMPORIO_ROLE_ID,
    "Contrabbando": CONTRABBANDO_ID,
    "Diligenza":    1421007310771191829,
    "Banchiere":    BANKER_ROLE_ID,
    "Distilleria":  DISTILL_ROLE_ID,
    "FightClub":    FIGHT_ROLE_ID,
    "Macelleria":   MACELLERIA_ROLE_ID,
}

# ── Helper permessi ───────────────────────────
def has_staff(interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.id in STAFF_ROLES for r in interaction.user.roles)

def has_sceriffo(interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.id in SCERIFFO_ROLES for r in interaction.user.roles)

def has_role_id(interaction, role_id) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    if isinstance(role_id, list):
        return any(r.id in role_id for r in interaction.user.roles)
    return any(r.id == role_id for r in interaction.user.roles)
