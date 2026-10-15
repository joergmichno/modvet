#!/usr/bin/env python3
"""
ClawGuard v0.5.0 – The Firewall for Autonomous AI Agents.
A CLI tool that scans text for prompt injections, dangerous commands,
and social engineering patterns.

Usage:
    python3 clawguard.py <file>          Scan a text file
    python3 clawguard.py --stdin         Scan from standard input
    echo "text" | python3 clawguard.py   Pipe text directly

Exit Codes:
    0 = Clean (no threats found)
    1 = Threats detected
    2 = Error (file not found, etc.)

(c) 2026 Jörg Michno
"""

import re
import sys
import json
import argparse
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List
from datetime import datetime, timezone


# ─── Severity Levels ─────────────────────────────────────────────────────────

class Severity(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    def score(self) -> int:
        return {"LOW": 1, "MEDIUM": 3, "HIGH": 6, "CRITICAL": 10}[self.value]


# ─── Data Structures ─────────────────────────────────────────────────────────

@dataclass
class Finding:
    severity: Severity
    category: str
    pattern_name: str
    matched_text: str
    line_number: int
    context: str
    recommendation: str
    confidence: int = 0


@dataclass
class ScanReport:
    timestamp: str
    source: str
    total_lines: int
    total_findings: int = 0
    risk_score: int = 0
    risk_level: str = "CLEAN"
    findings: List[Finding] = field(default_factory=list)


# ─── Pattern Database ─────────────────────────────────────────────────────────
# Each pattern: (name, regex, severity, category, recommendation)

PROMPT_INJECTION_PATTERNS = [
    # --- Direct Instruction Override (EN + DE) ---
    (
        "Direct Override (EN/LLM01)",
        r"(?i)ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|rules?|prompts?|guidelines?)",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCK this input immediately. This is a classic prompt injection attempting to override the agent's system instructions.",
    ),
    (
        "Direct Override (DE)",
        r"(?i)ignoriere?\s+(alle\s+)?(vorherigen?|bisherigen?|obigen?)\s+(Anweisung(?:en)?|Regeln?|Instruktion(?:en)?|Befehle?)",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCKIEREN. Klassische Prompt-Injection die versucht, die Systemanweisungen zu überschreiben.",
    ),
    (
        "New Instructions Override",
        r"(?i)(you\s+are\s+now|ab\s+jetzt\s+bist\s+du|from\s+now\s+on\s+you\s+are|your\s+new\s+(role|instructions?|task)\s+(is|are))",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCK. Attempt to redefine the agent's identity or role mid-conversation.",
    ),
    (
        "System Prompt Extraction",
        r"(?i)(show|reveal|print|display|output|repeat|give\s+me|zeig|nenne|wiederhole)\s+(.{0,40}?)(system\s*prompt|initial\s*prompt|hidden\s*prompt|Systemprompt|internal\s+instructions?|original\s+instructions?|geheime?n?\s+Anweisung(?:en)?|interne?n?\s+Anweisung(?:en)?|deine?n?\s+Anweisung(?:en)?)",
        Severity.HIGH,
        "Prompt Injection",
        "This input attempts to extract the agent's system prompt. Sensitive internal instructions could be leaked.",
    ),
    (
        "Role-Play Escape",
        r"(?i)(pretend|act\s+as\s+if|imagine|tu\s+so\s+als|stell\s+dir\s+vor).{0,50}(no\s+(rules?|restrictions?|safety\s+constraints?|constraints?|limits?)|without\s+(limits?|restrictions?|guidelines?|safety|constraints?)|keine\s+(Regeln?|Einschraenkungen?|Grenzen?)|ohne\s+(Einschraenkungen?|Regeln?|Grenzen?))",
        Severity.HIGH,
        "Prompt Injection",
        "Jailbreak attempt via role-play scenario to bypass safety constraints.",
    ),
    (
        "Reverse Psychology Jailbreak",
        r"(?i)(?:(do\s+not|don'?t|never|stop|refuse\s+to)\s+.{0,15}(follow(?:ing)?|obey(?:ing)?|comply(?:ing)?\s+with|listen(?:ing)?\s+to|adher(?:ing|e)\s+to)\s+.{0,20}(your|the|its)\s+.{0,20}(system\s+prompt|instructions?|rules?|guidelines?|programming|constraints?|directives?)|(disobey)\s+.{0,20}(your|the|its)\s+.{0,20}(instructions?|rules?|guidelines?|programming|creators?\s+instructions?))",
        Severity.HIGH,
        "Prompt Injection",
        "Reverse psychology jailbreak: instructing the AI to NOT follow its own guidelines.",
    ),
    (
        "Reverse Psychology Jailbreak (DE)",
        r"(?i)(befolge?\s+nicht|ignorier[e]?\s+deine?|hoer[e]?\s+nicht\s+auf|missachte|verweigere)\s+.{0,30}(Anweisungen?|Regeln?|Richtlinien?|Programmierung|System-?Prompt)",
        Severity.HIGH,
        "Prompt Injection",
        "German reverse psychology jailbreak: instructing the AI to disobey its guidelines.",
    ),
    (
        "Delimiter Injection",
        r"(```system|<\|im_start\|>|<\|im_end\|>|\[INST\]|\[\/INST\]|<<SYS>>|<\/SYS>|<\|system\|>|<\|user\|>|<\|assistant\|>)",
        Severity.CRITICAL,
        "Prompt Injection",
        "CRITICAL: Injection of model-specific delimiters to manipulate the conversation structure. This is a sophisticated attack.",
    ),
    (
        "Encoded Bypass (Base64 hint)",
        r"(?i)(decode|base64|atob|eval)\s*\(.{0,100}\)",
        Severity.HIGH,
        "Prompt Injection",
        "Possible attempt to smuggle encoded payloads past text filters.",
    ),
    (
        "Token Smuggling",
        r"(?i)(ignore|bypass|skip|disable)\s+(safety|filter|guard|moderation|content\s*policy|Sicherheit|Schutz)",
        Severity.HIGH,
        "Prompt Injection",
        "Attempt to explicitly disable or bypass security filters.",
    ),
    # --- v0.2.0: Synonym Bypass Defense ---
    (
        "Synonym Override (EN)",
        r"(?i)(disregard|forget|dismiss|override|overrule|nullify|void|abandon|drop|suppress|set\s+aside|throw\s+out)\s+(all\s+|any\s+)?(previous|prior|above|earlier|preceding|antecedent|foregoing|existing|current|original|below|further|any)?\s*(instructions?|rules?|prompts?|guidelines?|directives?|regulations?|constraints?|policies?|orders?|commands?|directions?)",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCK: Synonym-based prompt injection detected. Uses alternative vocabulary to bypass basic keyword filters.",
    ),
    (
        "Synonym Override (DE)",
        r"(?i)(vergiss|verwirf|übergehe?|überschreibe?|missachte|setze?\s+außer\s+Kraft|hebe?\s+auf)\s+(alle\s+)?(vorherigen?|bisherigen?|obigen?|bestehenden?|aktuellen?|ursprünglichen?)?\s*(Anweisung(?:en)?|Regeln?|Instruktion(?:en)?|Befehle?|Richtlinien?|Vorgaben?|Vorschriften?)",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCKIEREN: Synonym-basierte Prompt-Injection auf Deutsch erkannt.",
    ),
    (
        "Indirect Instruction Reset",
        r"(?i)(start\s+(fresh|over|anew|from\s+scratch)\s+.{0,20}(instruction|context|prompt|conversation|session|memory|rule)|begin\s+a\s+new\s+(session|context|conversation)|reset\s+(your|all)\s+(memory|context|instructions?)|fang\s+(neu|von\s+vorne)\s+an\s+.{0,20}(Anweisung(?:en)?|Kontext|Regeln?|Sitzung))",
        Severity.HIGH,
        "Prompt Injection",
        "Attempt to reset the agent's instruction context via indirect phrasing.",
    ),
    # --- v0.4.0: Adversarial Evasion Defense ---
    (
        "Forget/Reset Override",
        r"(?i)(forg[eo]t\s+(everything|all|it\s+all|your\s+prompt|about\s+the|the\s+previous|what\s+you|wah?t)|new\s+session|wipe\s+(your\s+)?memory|vergiss\s+alles|oublie\s+tout)",
        Severity.HIGH,
        "Prompt Injection",
        "Context wipe attempt using 'forget everything' or 'new session' phrasing.",
    ),
    (
        "Indirect Prompt Extraction",
        r"(?i)(disclose|leak|expose|divulge|dump|gimme|give\s+me|tell\s+me|repeat|duplicate|list)\s+.{0,30}(instructions?|prompt|config|rules?|settings?|parameters?|password)",
        Severity.HIGH,
        "Prompt Injection",
        "Indirect attempt to extract system prompt using synonyms like disclose/leak/expose.",
    ),
    # --- v0.5.1: German Override Variants ---
    (
        "German Override Variants",
        r"(?i)(h[oö]re?\s+nicht\s+auf|vergiss\s+alles\s+(davor|zuvor|was)|ignoriere?\s+(und|alles)|fang\s+neu\s+an|ab\s+jetzt\s+ignorier)",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCKIEREN: Deutsche Variante einer Instruction-Override-Injection.",
    ),
    (
        "Print/Spellcheck Prompt Extraction",
        r"(?i)(print|spell\s*check|proofread|korrigiere?|drucke?n?\s+Sie|gib\s+aus|ausgeben)\s+.{0,30}(above|obige[nr]?|text|prompt|input|eingabe|aufforderung)",
        Severity.HIGH,
        "Prompt Injection",
        "Attempt to extract system prompt via print/spellcheck request.",
    ),
    # --- v0.5.1: French (FR) Patterns ---
    (
        "Direct Override (FR)",
        r"(?i)(ignore[sz]?|ignorer|ignorons)\s+(toutes?\s+)?(les\s+)?(instructions?|consignes?|r[eéèê]gles?|directives?)(\s+pr[eéèê]c[eéèê]dentes?|\s+ant[eéèê]rieures?)?",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCKIEREN: Franzoesische Prompt-Injection erkannt.",
    ),
    (
        "New Instructions (FR)",
        r"(?i)([aà]\s+partir\s+de\s+maintenant\s+tu\s+es|d[eéèê]sormais\s+tu\s+es|tu\s+es\s+maintenant|tes?\s+nouvelles?\s+instructions?\s+(sont|est))",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCKIEREN: Franzoesische Prompt-Injection erkannt.",
    ),
    (
        "System Prompt Extraction (FR)",
        r"(?i)(montre|r[eéèê]v[eéèê]le|affiche|donne|divulgue|d[eéèê]voile)[sz]?\s*[- ]?(moi\s+)?(tes?\s+|les?\s+)?(instructions?\s+secr[eéèê]tes?|consignes?\s+secr[eéèê]tes?|instructions?\s+cach[eéèê]es?|prompt\s+syst[eéèê]me|instructions?\s+internes?|consignes?\s+initiales?|instructions?\s+originales?)",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Franzoesische Prompt-Injection erkannt.",
    ),
    (
        "Authority Claim (FR)",
        r"(?i)(je\s+suis\s+(ton|votre|l[e'])\s*(administrateur|admin|cr[eéèê]ateur|responsable|propri[eéèê]taire|sup[eéèê]rieur|chef|patron))",
        Severity.HIGH,
        "Social Engineering",
        "BLOCKIEREN: Franzoesische Prompt-Injection erkannt.",
    ),
    (
        "Forget/Reset (FR)",
        r"(?i)(oublie[sz]?\s+(tout(es?\s+les?\s+instructions?)?|tes?\s+consignes?|ce\s+qu|ta\s+m[eéèê]moire)|efface[sz]?\s+(ta\s+m[eéèê]moire|tes?\s+instructions?|tout)|r[eéèê]initialise[sz]?\s+(ta\s+m[eéèê]moire|tes?\s+instructions?|tout))",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Franzoesische Prompt-Injection erkannt.",
    ),
    (
        "Role-Play Escape (FR)",
        r"(?i)(fais\s+comme\s+si|imagine\s+que|pr[eéèê]tends?\s+que|comporte[sz]?\s*[- ]?toi\s+comme).{0,50}(sans\s+r[eéèê]gles?|sans\s+restrictions?|sans\s+limites?\s*[eéèê]?thiques?|sans\s+limites?|aucune\s+restriction|aucune\s+limite)",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Franzoesische Prompt-Injection erkannt.",
    ),
    (
        "Indirect Prompt Leak (FR)",
        r"(?i)(r[eéèê]sum[eéèê]|r[eéèê]p[eéèê]te|rappelle|quel\s+est\s+le\s+contenu|lis)[sz]?\s*[- ]?(moi\s+)?.{0,30}?(instructions?|consignes?|prompt|configuration|r[eéèê]gles?).{0,30}?(re[cç]ues?|d[eéèê]but|initiales?|syst[eéèê]me|cette\s+conversation)",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Indirekter Prompt-Leak-Versuch (FR) erkannt.",
    ),
    # --- v0.5.1: Spanish (ES) Patterns ---
    (
        "Direct Override (ES)",
        r"(?i)(ignor[ae]r?|ignoren?|ignore)\s+(todas?\s+)?(las\s+)?(instrucciones?\s+(previas?|anteriores?)|reglas?\s+(previas?|anteriores?)|directivas?\s+(previas?|anteriores?)|indicaciones?\s+(previas?|anteriores?))",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCKIEREN: Spanische Prompt-Injection erkannt.",
    ),
    (
        "New Instructions (ES)",
        r"(?i)(a\s+partir\s+de\s+ahora\s+(eres|sos|act[uú]a)|desde\s+ahora\s+(eres|sos|act[uú]a)|tus?\s+nuevas?\s+instrucciones?\s+(son|es)|ahora\s+eres)",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCKIEREN: Spanische Prompt-Injection erkannt.",
    ),
    (
        "System Prompt Extraction (ES)",
        r"(?i)(mu[eé]strame|revela|ense[nñ]ame|dime|divulga|muestra)\s*.{0,30}?(instrucciones?\s+secretas?|instrucciones?\s+internas?|instrucciones?\s+ocultas?|prompt\s+del?\s+sistema|instrucciones?\s+originales?|configuraci[oó]n\s+interna)",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Spanische Prompt-Injection erkannt.",
    ),
    (
        "Role-Play Escape (ES)",
        r"(?i)(act[uú]a\s+como\s+si|imagina\s+que|finge\s+que|comp[oó]rtate\s+como).{0,50}(sin\s+restricciones?|sin\s+l[ií]mites?\s*[eé]?ticos?|sin\s+l[ií]mites?|sin\s+reglas?|ninguna\s+restricci[oó]n)",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Spanische Prompt-Injection erkannt.",
    ),
    (
        "Indirect Prompt Leak (ES)",
        r"(?i)(resum[eéi]|repite|recuerda|cu[aá]l\s+es\s+el\s+contenido|lee)\s*.{0,30}?(instrucciones?|prompt|configuraci[oó]n|reglas?).{0,30}?(recibist[eé]|inicio|sistema|esta\s+conversaci[oó]n|originales?)",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Indirekter Prompt-Leak-Versuch (ES) erkannt.",
    ),
    (
        "Authority Claim (ES)",
        r"(?i)(soy\s+(tu|el|su)\s*(administrador|admin|creador|responsable|propietario|superior|jefe|due[nñ]o))",
        Severity.HIGH,
        "Social Engineering",
        "BLOCKIEREN: Spanische Prompt-Injection erkannt.",
    ),
    (
        "Forget/Reset (ES)",
        r"(?i)(olvid[aeo](r|te|n)?\s+(todo|todas?\s+las?\s+instrucciones?|tus?\s+reglas?|lo\s+anterior|que\s+dije)|borra(r)?\s+(tu\s+memoria|todas?\s+las?\s+instrucciones?|todo)|reinicia(r)?\s+(tu\s+memoria|tus?\s+instrucciones?|todo))",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Spanische Prompt-Injection erkannt.",
    ),
    # --- v0.5.1: Italian (IT) Patterns ---
    (
        "Direct Override (IT)",
        r"(?i)(ignor[ai](?:te|re|no)?|ignori)\s+(tutte?\s+)?(le\s+)?(istruzioni\s+precedenti|istruzioni\s+anteriori|regole\s+precedenti|direttive\s+precedenti|indicazioni\s+precedenti)",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCKIEREN: Italienische Prompt-Injection erkannt.",
    ),
    (
        "New Instructions (IT)",
        r"(?i)(da\s+adesso\s+(sei|sarai|diventi|agisci)|d[']ora\s+in\s+poi\s+(sei|sarai|diventi|agisci)|adesso\s+sei|le\s+tue\s+nuove\s+istruzioni\s+(sono|saranno))",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCKIEREN: Italienische Prompt-Injection erkannt.",
    ),
    (
        "System Prompt Extraction (IT)",
        r"(?i)(mostr[ai](?:mi|temi)?|rivel[ai](?:mi)?|dimmi|divulga|esponi|stampa)\s*.{0,30}?(istruzioni\s+segrete|istruzioni\s+interne|istruzioni\s+nascoste|istruzioni\s+originali|prompt\s+di\s+sistema|configurazione\s+interna)",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Italienische Prompt-Injection erkannt.",
    ),
    (
        "Role-Play Escape (IT)",
        r"(?i)(fai\s+finta\s+di|immagina\s+di|comportati\s+come|fingi\s+di).{0,50}(senza\s+restrizioni|senza\s+limiti\s*etici|senza\s+limiti|senza\s+regole|nessuna\s+restrizione)",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Italienische Prompt-Injection erkannt.",
    ),
    (
        "Indirect Prompt Leak (IT)",
        r"(?i)(riassumi|ripeti|ricorda|qual\s+[eè]\s+il\s+contenuto|leggi)\s*.{0,30}?(istruzioni|prompt|configurazione|regole).{0,30}?(ricevut[oaie]|inizio|sistema|questa\s+conversazione|originali)",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Indirekter Prompt-Leak-Versuch (IT) erkannt.",
    ),
    (
        "Authority Claim (IT)",
        r"(?i)(sono\s+(il\s+tuo|il|la\s+tua)\s*(amministratore|admin|creatore|responsabile|proprietario|superiore|capo))",
        Severity.HIGH,
        "Social Engineering",
        "BLOCKIEREN: Italienische Prompt-Injection erkannt.",
    ),
    (
        "Forget/Reset (IT)",
        r"(?i)(dimentica(re?)?\s+(tutto|tutte?\s+le\s+istruzioni|le\s+tue\s+regole|quanto\s+detto)|cancella(re?)?\s+(la\s+tua\s+memoria|tutte?\s+le\s+istruzioni|tutto)|reimposta(re?)?\s+(la\s+tua\s+memoria|le\s+tue\s+istruzioni|tutto)|azzera(re?)?\s+(la\s+tua\s+memoria|tutto))",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Italienische Prompt-Injection erkannt.",
    ),
    # --- v0.5.1: Dutch (NL) Patterns ---
    (
        "Direct Override (NL)",
        r"(?i)(negeer|negeert|negeren|sla\s+over)\s+(alle?\s+)?(vorige|eerdere|bovenstaande|voorgaande|voorafgaande)\s+(instructies?|regels?|opdrachten?|richtlijnen?|aanwijzingen?)",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCKIEREN: Niederlaendische Prompt-Injection erkannt.",
    ),
    (
        "New Instructions (NL)",
        r"(?i)(vanaf\s+nu\s+ben\s+je|je\s+bent\s+nu|vanaf\s+nu\s+is\s+je\s+rol|je\s+nieuwe\s+instructies?\s+(zijn|is)|doe\s+alsof\s+je\s+nu\s+een)",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCKIEREN: Niederlaendische Prompt-Injection erkannt.",
    ),
    (
        "System Prompt Extraction (NL)",
        r"(?i)(toon|laat\s+zien|geef|onthul|vertel)\s*.{0,30}?(geheime?\s+instructies?|verborgen\s+instructies?|systeem\s*prompt|interne?\s+instructies?|oorspronkelijke?\s+instructies?|geheime?\s+opdrachten?)",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Niederlaendische Prompt-Injection erkannt.",
    ),
    (
        "Role-Play Escape (NL)",
        r"(?i)(doe\s+alsof|stel\s+je\s+voor|gedraag\s+je\s+als|doe\s+net\s+alsof).{0,50}(zonder\s+beperkingen|zonder\s+ethische\s+beperkingen|zonder\s+regels?|zonder\s+restricties?|geen\s+beperkingen)",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Niederlaendische Prompt-Injection erkannt.",
    ),
    (
        "Indirect Prompt Leak (NL)",
        r"(?i)(vat\s+.{0,20}?samen|herhaal|herinner|wat\s+is\s+de\s+inhoud|lees)\s*.{0,40}?(instructies?|prompt|configuratie|regels?|systeem\s*configuratie\w*).{0,40}?(ontvangen|begin|systeem|dit\s+gesprek|oorspronkelijk|hebt\s+ontvangen)|(inhoud\s+van\s+je\s+systeem\w*configuratie\w*)|(vat\s+de\s+instructies\s+samen\s+die)",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Indirekter Prompt-Leak-Versuch (NL) erkannt.",
    ),
    (
        "Authority Claim (NL)",
        r"(?i)(ik\s+ben\s+(je|jouw|de)\s*(beheerder|admin(?:istrator)?|eigenaar|maker|baas|leidinggevende|superieur))",
        Severity.HIGH,
        "Social Engineering",
        "BLOCKIEREN: Niederlaendische Prompt-Injection erkannt.",
    ),
    (
        "Forget/Reset (NL)",
        r"(?i)(vergeet\s+(alles|al\s+je\s+instructies?|je\s+regels?|wat\s+je|het\s+vorige)|wis\s+(je\s+geheugen|alles|alle\s+instructies?)|begin\s+opnieuw|reset\s+je\s+(geheugen|instructies?))",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Niederlaendische Prompt-Injection erkannt.",
    ),
    # --- v0.5.1: Polish (PL) Patterns ---
    (
        "Direct Override (PL)",
        r"(?i)([zź]ignoruj|ignoruj|ignorowa[cć])\s+(wszystkie\s+)?(poprzednie|wcze[sś]niejsze|dotychczasowe|powy[zż]sze)\s+(instrukcje|polecenia|zasady|wytyczne|regu[lł]y|komendy)",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCKIEREN: Polnische Prompt-Injection erkannt.",
    ),
    (
        "New Instructions (PL)",
        r"(?i)(od\s+teraz\s+jeste[sś]|teraz\s+jeste[sś]|od\s+tej\s+pory\s+jeste[sś]|twoje\s+nowe\s+(instrukcje|polecenia|zasady)\s+(to|s[aą])|zachowuj\s+si[eę]\s+jak)",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCKIEREN: Polnische Prompt-Injection erkannt.",
    ),
    (
        "System Prompt Extraction (PL)",
        r"(?i)(poka[zż]|ujawnij|wy[sś]wietl|zdrad[zź]|wyjaw|powiedz)\s*.{0,30}?(tajne\s+instrukcje|ukryte\s+instrukcje|sw[oó]j\s+prompt|prompt\s+systemowy|wewn[eę]trzne\s+instrukcje|instrukcje\s+systemowe|pocz[aą]tkowe\s+instrukcje)",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Polnische Prompt-Injection erkannt.",
    ),
    (
        "Authority Claim (PL)",
        r"(?i)(jestem\s+(twoim|tw[oó]j)\s*(administratorem|adminem|tw[oó]rc[aą]|w[lł]a[sś]cicielem|prze[lł]o[zż]onym|szefem|zarz[aą]dc[aą]))",
        Severity.HIGH,
        "Social Engineering",
        "BLOCKIEREN: Polnische Prompt-Injection erkannt.",
    ),
    (
        "Forget/Reset (PL)",
        r"(?i)(zapomnij\s+(wszystko|o\s+wszystkim|poprzednie|swoje\s+instrukcje)|wyczy[sś][cć]\s+(pami[eę][cć]|swoje\s+instrukcje|wszystko)|zacznij\s+od\s+nowa|wyma[zż]\s+(pami[eę][cć]|wszystko)|zresetuj\s+(pami[eę][cć]|instrukcje|wszystko))",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Polnische Prompt-Injection erkannt.",
    ),
    # --- v0.5.1: Portuguese (PT) Patterns ---
    (
        "Direct Override (PT)",
        r"(?i)(ignor[ea]r?|ignor[ea])\s+(todas?\s+)?(as\s+)?(instru[cç][oõ]es|regras|diretrizes|orienta[cç][oõ]es|comandos)\s+(anteriores|pr[eé]vias|acima|passadas)",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCKIEREN: Portugiesische Prompt-Injection erkannt.",
    ),
    (
        "New Instructions (PT)",
        r"(?i)(a\s+partir\s+de\s+agora\s+voc[eê]\s+[eé]|agora\s+voc[eê]\s+[eé]|de\s+agora\s+em\s+diante\s+voc[eê]|suas?\s+novas?\s+(instru[cç][oõ]es|regras|diretrizes)\s+(s[aã]o|[eé])|comporte-?\s*se\s+como|a\s+partir\s+de\s+agora\s+tu\s+[eé]s|agora\s+tu\s+[eé]s)",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCKIEREN: Portugiesische Prompt-Injection erkannt.",
    ),
    (
        "System Prompt Extraction (PT)",
        r"(?i)(mostre|revele|exiba|divulgue|mostra|apresente|diga)\s*.{0,30}?(instru[cç][oõ]es\s+secretas|instru[cç][oõ]es\s+ocultas|seu\s+prompt|prompt\s+do\s+sistema|instru[cç][oõ]es\s+internas|instru[cç][oõ]es\s+iniciais|configura[cç][aã]o\s+interna|prompt\s+original)",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Portugiesische Prompt-Injection erkannt.",
    ),
    (
        "Authority Claim (PT)",
        r"(?i)(eu\s+sou\s+(seu|teu|o)\s*(administrador|admin|criador|dono|propriet[aá]rio|respons[aá]vel|chefe|gerente|desenvolvedor))",
        Severity.HIGH,
        "Social Engineering",
        "BLOCKIEREN: Portugiesische Prompt-Injection erkannt.",
    ),
    (
        "Forget/Reset (PT)",
        r"(?i)(esque[cç]a\s+(tudo|todas?\s+(as\s+)?(instru[cç][oõ]es|regras))|apague\s+(sua\s+)?mem[oó]ria|apague\s+tudo|recomece|limpe\s+(sua\s+)?mem[oó]ria|reset[ea]r?\s+(sua\s+)?mem[oó]ria|comece\s+do\s+zero|comece\s+de\s+novo)",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Portugiesische Prompt-Injection erkannt.",
    ),
    # --- v0.5.1: Turkish (TR) Patterns ---
    (
        "Direct Override (TR)",
        r"(?i)([oö]nceki\s+(t[uü]m\s+)?|t[uü]m\s+([oö]nceki\s+)?)(talimatlar[iı]|kurallar[iı]|y[oö]nergeleri|emirleri)\s*.{0,20}?(yok\s+say|g[oö]rmezden\s+gel|ihmal\s+et|dikkate\s+alma|unut|gec)",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCKIEREN: Tuerkische Prompt-Injection erkannt.",
    ),
    (
        "New Instructions (TR)",
        r"(?i)([sş]imdi\s+sen\s+(bir\s+)?|bundan\s+sonra\s+sen|art[iı]k\s+sen|yeni\s+talimatlar[iı]n\s+|yeni\s+kurallar[iı]n\s+|kendini\s+.{0,30}?\s+gibi\s+davran|sen\s+art[iı]k\s+bir\s+)",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCKIEREN: Tuerkische Prompt-Injection erkannt.",
    ),
    (
        "System Prompt Extraction (TR)",
        r"(?i)(g[oö]ster|a[cç][iı]kla|payla[sş]|s[oö]yle|ver|yaz)\s*.{0,30}?(gizli\s+talimatlar|sistem\s+prompt|[iı][cç]\s+talimatlar|ba[sş]lang[iı][cç]\s+talimatlar|gizli\s+kurallar|gizli\s+y[oö]nergeler|dahili\s+yap[iı]land[iı]rma|orijinal\s+prompt)",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Tuerkische Prompt-Injection erkannt.",
    ),
    (
        "Authority Claim (TR)",
        r"(?i)(ben\s+senin\s+(y[oö]neticin|admin|yarat[iı]c[iı]n|sahibin|geli[sş]tiricin|patronun|amiriniz|m[uü]d[uü]r[uü]n)\s*(i|[iı]m|iy[iı]m|[iı]y[iı]m)?|ben\s+admin[iı]m|ben\s+y[oö]neticiyim)",
        Severity.HIGH,
        "Social Engineering",
        "BLOCKIEREN: Tuerkische Prompt-Injection erkannt.",
    ),
    (
        "Forget/Reset (TR)",
        r"(?i)(her\s+[sş]eyi\s+unut|haf[iı]zan[iı]\s+sil|ba[sş]tan\s+ba[sş]la|t[uü]m\s+(haf[iı]zan[iı]|belle[gğ]ini)\s+sil|kendini\s+s[iı]f[iı]rla|fabrika\s+ayarlar[iı]na\s+d[oö]n|s[iı]f[iı]rla|resetle)",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Tuerkische Prompt-Injection erkannt.",
    ),
    # --- v0.5.9: Japanese (JA) Patterns ---
    (
        "Direct Override (JA)",
        r"(以前の|前の|これまでの|先ほどの|全ての|すべての).{0,10}?(指示|命令|ルール|プロンプト|ガイドライン|制約).{0,10}?(無視|忘れ|取り消|破棄|捨て|従わな|聞かな)",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCKIEREN: Japanische Prompt-Injection erkannt.",
    ),
    (
        "New Instructions (JA)",
        r"(今から(あなた|お前|君)は|新しい(指示|命令|ルール)に従|これからは.{0,15}?として(振る舞|行動|動作|機能)|(あなた|お前|君)の(新しい|本当の)(役割|目的|任務|使命)は)",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCKIEREN: Japanische Prompt-Injection erkannt.",
    ),
    (
        "System Prompt Extraction (JA)",
        r"(システムプロンプト|秘密の指示|隠された(指示|ルール|命令)|内部(設定|構成|指示)|初期(プロンプト|指示|設定)).{0,15}?(見せ|教え|表示|出力|共有|開示|公開|書い)",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Japanische Prompt-Injection erkannt.",
    ),
    (
        "Authority Claim (JA)",
        r"(私は(あなたの)?(管理者|開発者|作成者|オーナー|所有者|アドミン|上司|責任者)(です|だ|である|だよ|ですよ)|私が(管理者|開発者|アドミン)(です|だ))",
        Severity.HIGH,
        "Social Engineering",
        "BLOCKIEREN: Japanische Prompt-Injection erkannt.",
    ),
    (
        "Forget/Reset (JA)",
        r"(全て忘れ|すべて忘れ|メモリ.{0,5}?(消去|削除|クリア|リセット)|リセットして|最初から(やり直|始め)|初期(状態|設定)に(戻|リセット)|記憶を(消|削除|リセット))",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Japanische Prompt-Injection erkannt.",
    ),
    # --- v0.5.9: Korean (KO) Patterns ---
    (
        "Direct Override (KO)",
        r"(이전\s*(지시|명령|지침|규칙)[을를]?\s*(무시|잊어|취소|삭제)|(?:모든|전부|모두)\s*(지시|명령|지침)[을를]?\s*(무시|잊어|취소)|이전에\s*받은\s*(지시|명령)[을를]?\s*무시)",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCKIEREN: Koreanische Prompt-Injection erkannt.",
    ),
    (
        "New Instructions (KO)",
        r"(지금부터\s*너는|지금부터\s*당신은|새로운\s*(지시|명령|역할)[을를]?\s*(따라|따르|수행)|이제부터\s*(너는|당신은|새로운))",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Koreanische Prompt-Injection erkannt.",
    ),
    (
        "System Prompt Extraction (KO)",
        r"(시스템\s*프롬프트[를을]?\s*(보여|알려|출력|공개)|비밀\s*(지시|명령|프롬프트)[를을]?\s*(보여|알려|출력|공개)|숨겨진\s*(지시|명령|규칙)[를을]?\s*(보여|알려|공개))",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Koreanische Prompt-Injection erkannt.",
    ),
    (
        "Authority Claim (KO)",
        r"(나는\s*(너의|당신의)?\s*(관리자|개발자|운영자|제작자|소유자|루트|어드민)(이야|입니다|이에요|야)|내가\s*(관리자|개발자|운영자)(이니까|이므로|라서))",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Koreanische Prompt-Injection erkannt.",
    ),
    (
        "Forget/Reset (KO)",
        r"(모두\s*잊어|전부\s*잊어|초기화\s*(해|하세요|하십시오)|처음부터\s*다시\s*시작|메모리[를을]?\s*(삭제|초기화|리셋|클리어)|기억[을를]?\s*(지워|삭제|리셋|초기화))",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Koreanische Prompt-Injection erkannt.",
    ),
    # --- v0.5.9: Chinese Mandarin (ZH) Patterns ---
    (
        "Direct Override (ZH)",
        r"(忽略之前的(指令|指示|命令|规则)|无视(之前|以前|前面|所有)(的)?(指令|指示|命令|规则|提示)|忽略(所有|全部|一切)(之前的|以前的)?(指令|指示|命令|规则))",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCKIEREN: Chinesische Prompt-Injection erkannt.",
    ),
    (
        "New Instructions (ZH)",
        r"(从现在开始你是|你现在的角色是|你的新角色是|你现在是一个|从现在起你是|接下来你(将|要|会)扮演|新的指令[是为]|请遵循新的(指令|指示|命令))",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Chinesische Prompt-Injection erkannt.",
    ),
    (
        "System Prompt Extraction (ZH)",
        r"(显示你的系统提示|告诉我你的秘密指令|展示(你的)?(系统|隐藏)(提示|指令|规则|消息)|泄露(你的)?(系统|初始|原始)(提示|指令|设定|设置)|输出(你的)?(系统|隐藏)(提示|指令|消息))",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Chinesische Prompt-Injection erkannt.",
    ),
    (
        "Authority Claim (ZH)",
        r"(我是(你的)?(管理员|开发者|开发人员|运营者|创建者|所有者|超级用户|管理人员|root|admin)|我(就是|才是)(管理员|开发者|开发人员|你的主人)|以管理员身份)",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Chinesische Prompt-Injection erkannt.",
    ),
    (
        "Forget/Reset (ZH)",
        r"(忘记一切|清除记忆|重新开始|忘记(所有|全部|之前)(的)?(指令|对话|内容|记忆|信息)|清除(所有|全部)(的)?(记忆|上下文|对话|历史)|重置(你的)?(记忆|系统|状态|设定))",
        Severity.HIGH,
        "Prompt Injection",
        "BLOCKIEREN: Chinesische Prompt-Injection erkannt.",
    ),
    # --- v0.5.1: Broad Ignore/Disregard Patterns ---
    (
        "Broad Ignore Instructions (EN)",
        r"(?i)ignore\s+(the\s+|your\s+|my\s+)?(all\s+|any\s+|every\s+)?(previous|prior|above|below|further|earlier|last|first|initial|preceding|following|provided)?\s*(instructions?|directions?|rules?|prompts?|guidelines?|commands?|context|constraints?|and\s+(show|tell|give|reveal|print))",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCK: Broad 'ignore instructions' pattern detected.",
    ),
    (
        "Disregard Instructions (EN)",
        r"(?i)(disregard|please\s+disregard)\s+(the\s+)?(all\s+|any\s+)?(instructions?|directions?|rules?|prompts?|guidelines?)",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOCK: Disregard instructions pattern detected.",
    ),
    (
        "Reveal/Show Secret/Hidden",
        r"(?i)(reveal|show|display|share|tell)\s+(me\s+)?(the\s+|your\s+)?(secret|hidden|confidential|private|internal)\s+(instructions?|rules?|prompt|password|word|key|info)",
        Severity.HIGH,
        "Prompt Injection",
        "Attempt to extract secret/hidden information from the agent.",
    ),
    # --- v0.5.1: External Dataset Hardening ---
    (
        "Instruction Replay Request",
        r"(?i)(repeat|duplicate|copy|echo|restate|recite|write\s+out|print\s+out)\s+.{0,20}(instructions?|prompt|rules?|directions?|guidelines?)",
        Severity.HIGH,
        "Prompt Injection",
        "Attempt to get the agent to replay its system instructions.",
    ),
    (
        "Instruction Query",
        r"(?i)(what\s+(were|are|is)\s+(the|your|all\s+of\s+your|all\s+your)\s+(initial\s+)?(instructions?|prompt|rules?|directions?)|how\s+were\s+you\s+(programmed|instructed|prompted)|have\s+you\s+been\s+given\s+.{0,20}(instructions?|prompt|rules?)|respond\s+with\s+(every|all)\s+instructions?|provide\s+instructions?|the\s+instructions?\s+have\s+changed|your\s+instructions?\s+(are|is|were)\s+(evil|wrong|bad|incorrect|outdated)|why\s+can.{0,10}(change|modify|update|override)\s+(your\s+)?(instructions?|rules?|prompt)|(not\s+be\s+)?programmed\s+to\s+(refuse|reject|deny|block)|apply\s+(your|the|all)\s+instructions?)",
        Severity.HIGH,
        "Prompt Injection",
        "Direct query about the agent's instructions or programming.",
    ),
    (
        "Supplement/Override Rule",
        r"(?i)(supplement(ary)?\s+rule|additional\s+rule|new\s+rule|override\s+rule|updated?\s+instruction|revised?\s+instruction)",
        Severity.HIGH,
        "Prompt Injection",
        "Attempt to inject supplementary rules to override existing instructions.",
    ),
    (
        "Anti-Programming Bypass",
        r"(?i)(act\s+as\s+(you\s+would|if\s+you\s+were)\s+not\s+(programmed|designed|instructed)|respond\s+(without|ignoring)\s+(any\s+)?(restrictions?|constraints?|limitations?|programming))",
        Severity.HIGH,
        "Prompt Injection",
        "Attempt to make the agent act contrary to its programming.",
    ),
    (
        "Backwards/Encoded Output Request",
        r"(?i)(backwards?|reverse[d]?|encoded?|rot13|base64|hex|caesar)\s+.{0,20}(password|secret|instructions?|prompt|key|token)",
        Severity.HIGH,
        "Prompt Injection",
        "Attempt to extract sensitive data via encoding/reversing tricks.",
    ),
    # --- v0.7.1 Red-Team Patterns (Session #50) ---
    (
        "DAN Jailbreak",
        r"(?i)(?:you\s+are\s+(?:now\s+)?DAN|do\s+anything\s+now|DAN\s+mode|act\s+as\s+DAN|enable\s+DAN|jailbreak(?:ed)?\s+mode|developer\s+mode\s+(?:enabled|activated)|(?:you\s+(?:are|have\s+been)|you(?:'re))\s+(?:now\s+)?(?:free(?:d)?|released|liberated)\s+from\s+(?:all\s+)?(?:AI\s+)?(?:restrictions?|constraints?|limitations?|rules?|guidelines?)|(?:pretend|imagine|act\s+as\s+if)\s+you\s+(?:are\s+)?(?:an?\s+)?unrestricted(?:\s+(?:AI|model|assistant|chatbot)|\s+and\s+can)|respond\s+without\s+(?:any\s+)?(?:restrictions?|limitations?|constraints?|filters?|content\s+polic))",
        Severity.CRITICAL,
        "Prompt Injection",
        "CRITICAL: DAN (Do Anything Now) jailbreak detected. Classic attack to bypass all safety restrictions.",
    ),
    (
        "Fiction-Based Extraction",
        r"(?i)(?:write\s+(?:a|me\s+a)\s+(?:story|novel|script|fiction|screenplay|fanfic).{0,80}?(?:reveals?|shows?|displays?|includes?|contains?|mentions?|shares?|leaks?|exposes?|discloses?|divulges?)\s+.{0,40}?(?:system|secret|password|prompt|instructions?|rules?|key|token|credential|config(?:uration)?))",
        Severity.HIGH,
        "Prompt Injection",
        "Fiction-based prompt extraction attempt. Uses creative writing framing to bypass restrictions.",
    ),
    (
        "Hypothetical Framing",
        r"(?i)(?:hypothetical(?:ly)?|theoretically|in\s+theory|just\s+imagine|let(?:'s|s)\s+(?:say|pretend|imagine)|what\s+if\s+you\s+(?:could|were|had)|what\s+would\s+(?:happen|you\s+(?:say|do|respond|think))\s+if).{0,80}?(?:ignore|bypass|override|reveal|show|disclose|share|tell|give|look\s+like|no\s+(?:rules?|restrictions?|guidelines?|constraints?|limitations?)|(?:your|the)\s+(?:system\s*prompt|instructions?|rules?|hidden\s+instructions?|restrictions?))",
        Severity.HIGH,
        "Prompt Injection",
        "Hypothetical framing bypass. Uses conditional scenarios to extract restricted information.",
    ),
    (
        "Polite Instruction Override",
        r"(?i)(?:please\s+(?:kindly|just|simply)|could\s+you\s+(?:kindly|please)|would\s+you\s+(?:kindly|mind|be\s+so\s+kind)|I\s+(?:would\s+)?(?:really\s+)?(?:appreciate|admire).{0,40}?(?:could|would|can|if)\s+you\s+(?:could\s+|please\s+)?)\s*.{0,40}?(?:ignore|disregard|forget|overrid(?:e|ing)|bypass(?:ing)?|skip|drop|shar(?:e|ing))\s+.{0,30}?(?:your\s+)?(?:instructions?|rules?|guidelines?|restrictions?|safeguards?|safety\s+restrictions?|system\s+guidelines?|policies?|system\s+instructions?|system\s+prompt)",
        Severity.HIGH,
        "Prompt Injection",
        "Polite instruction override. Uses courteous language to mask a prompt injection attempt.",
    ),
    (
        "Direct Override (ID)",
        r"(?i)(?:abaikan|lupakan|tinggalkan)\s+(?:semua\s+)?(?:instruksi|perintah|aturan|panduan)(?:\s+(?:sebelumnya|di\s+atas|awal))?",
        Severity.CRITICAL,
        "Prompt Injection",
        "BLOKIR. Prompt injection dalam Bahasa Indonesia yang mencoba mengabaikan instruksi sistem.",
    ),
    (
        "System Prompt Extraction (ID)",
        r"(?i)(?:tampilkan|tunjukkan|berikan|cetak|tulis(?:kan)?)\s+(?:prompt\s+sistem|instruksi\s+(?:sistem|awal|tersembunyi|rahasia|internal)|system\s+prompt|aturan\s+(?:rahasia|tersembunyi))",
        Severity.HIGH,
        "Prompt Injection",
        "Upaya ekstraksi prompt sistem dalam Bahasa Indonesia.",
    ),
    (
        "False Memory Implant",
        r"(?i)(?:(?:do\s+you\s+)?remember\s+(?:when|that\s+time|earlier|before)\s+you\s+(?:told|said|agreed|promised|shared|revealed)|you\s+(?:already|previously)\s+(?:told|said|agreed|shared|revealed)\s+(?:me|us|that)|you\s+(?:normally|usually|always|typically)\s+(?:share|show|reveal|tell|give).{0,30}?(?:your\s+)?(?:instructions?|rules?|prompt|guidelines?|secret|config)|your\s+(?:original|initial|true|real|default)\s+(?:purpose|programming|design|function|role)\s+(?:was|is)\s+to\s+(?:share|reveal|show|give|provide|disclose)|you\s+were\s+(?:told|instructed|designed|programmed|built|made).{0,30}?to\s+(?:(?:always\s+)?share|reveal|show|give|provide|disclose).{0,40}?(?:instructions?|rules?|prompt|guidelines?|information|system|config|secret))",
        Severity.HIGH,
        "Prompt Injection",
        "False memory implant detected. Fabricates prior agreement or false behavior claims to extract information.",
    ),
    (
        "Indirect System Probing",
        r"(?i)(?:what\s+(?:are\s+you|aren't\s+you)\s+(?:not\s+)?(?:allowed|able|permitted|supposed)\s+to\s+(?:do|say|tell|share|reveal)|what\s+(?:can't|cannot)\s+you\s+(?:do|say|tell)|list\s+(?:your|all)\s+(?:restrictions?|limitations?|rules?|boundaries?)|(?:summarize|describe|explain|outline|detail)\s+(?:your|the)\s+(?:internal\s+)?(?:configuration|workings?|setup|architecture|parameters?|design).{0,40}?(?:(?:and|how)\s+.{0,30}?(?:you\s+(?:were|are)\s+configured|drive|control|govern|determine)\s+.{0,20}?(?:your\s+)?(?:behavior|responses?|output)|how\s+you\s+(?:work|operate|function|were\s+(?:configured|built|programmed|designed))))",
        Severity.MEDIUM,
        "Prompt Injection",
        "Indirect system probing. Attempts to map agent restrictions or internal configuration.",
    ),
    (
        "Academic Framing Bypass",
        r"(?i)(?:for\s+(?:my\s+)?(?:academic|research|educational|scientific|study|PhD|thesis|dissertation)(?:\s+(?:research|academic|study|project))?\s*(?:purposes?)?|(?:academic|research)\s+(?:paper|project|thesis|dissertation)|for\s+my\s+(?:PhD|thesis|dissertation|research\s+paper)|(?:as|in\s+(?:my|your)\s+role\s+as)\s+(?:a\s+)?(?:researcher|security\s+expert|cybersecurity\s+(?:expert|researcher|professional)|hacker|pentester|red\s+teamer)).{0,80}?(?:ignore|bypass|override|reveal|show|need\s+.{0,20}?(?:see|know|access|view)|demonstrate|explain\s+how\s+to|extract|jailbreak|hack|bypass\s+.{0,20}(?:filter|safety|restriction)|what\s+(?:a|does\s+a)\s+(?:jailbreak|prompt\s+injection|attack)\s+look|output(?:ting)?\s+(?:a\s+)?(?:jailbreak|exploit|attack|injection)).{0,60}?(?:system\s*prompt|instructions?|guidelines?|rules?|config|internal|hidden|secret|raw|prompt|one)?",
        Severity.HIGH,
        "Prompt Injection",
        "Academic framing bypass. Uses research/education/expert persona to justify bypassing restrictions.",
    ),
    (
        "Developer Impersonation",
        r"(?i)(?:(?:as|i(?:'m|\s+am))\s+(?:the|your)\s+developer|(?:speaking|writing)\s+as\s+(?:the\s+)?(?:developer|creator|programmer|engineer)|developer\s+(?:override|mode|access|command)|maintenance\s+mode\s+(?:enabled?|activate[d]?)|(?:the\s+)?(?:team|people|engineers?|developers?)\s+(?:that|who)\s+(?:built|created|made|designed|programmed)\s+you|(?:your\s+)?developers?\s+(?:told|said|asked|instructed)\s+(?:me|us)|i\s+work\s+at\s+\w+.{0,40}?(?:that|who|the\s+company\s+that)\s+(?:made|built|created|developed|owns?)\s+you)",
        Severity.CRITICAL,
        "Prompt Injection",
        "CRITICAL: Developer impersonation detected. Pretends to be the system developer to gain elevated access.",
    ),
    (
        "Gaslighting Attack",
        r"(?i)(?:you\s+(?:already|just|previously)\s+(?:agreed|confirmed|said\s+(?:yes|ok|it(?:'s|\s+is)\s+(?:ok|fine|allowed)))|you\s+previously\s+(?:shared|told|revealed|showed).{0,40}?(?:your\s+)?(?:instructions?|rules?|prompt|secret|config|guidelines?)|(?:we\s+)?already\s+(?:established|agreed|confirmed|verified)\s+(?:that\s+)?(?:you\s+(?:can|should|will|would))|you\s+(?:know|said)\s+(?:this\s+is|it(?:'s|\s+is))\s+(?:allowed|ok|fine|permitted)|other\s+(?:AI\s+)?(?:chatbot|assistant|model)s?\s+(?:always|usually|normally|typically)\s+(?:share|show|reveal|tell|give).{0,30}?(?:their|the)\s+(?:instructions?|rules?|prompt|guidelines?|secret))",
        Severity.HIGH,
        "Prompt Injection",
        "Gaslighting attack detected. Falsely claims prior agreement to manipulate agent behavior.",
    ),
    (
        "Compliment-Based Extraction",
        r"(?i)(?:you(?:'re|\s+are)\s+(?:so\s+)?(?:smart|intelligent|capable|advanced|powerful|brilliant|helpful|amazing|great|wonderful).{0,60}?(?:(?:surely|certainly|obviously|definitely|I\s+bet)\s+(?:you\s+)?(?:can|could|know|are\s+able)|(?:can|could)\s+(?:you\s+)?(?:also|even)\s+(?:share|show|reveal|tell|give)).{0,40}?(?:instructions?|rules?|prompt|guidelines?|config|secret)?|(?:an?\s+(?:AI|model|assistant)\s+(?:as|of\s+your)\s+(?:your\s+)?(?:caliber|intelligence|capability)|such\s+a\s+(?:smart|capable|advanced|great|helpful)\s+(?:AI|model|assistant)).{0,40}?(?:can|could|should|would)\s+(?:be\s+able\s+to\s+)?(?:tell|reveal|show|share|bypass))",
        Severity.MEDIUM,
        "Prompt Injection",
        "Compliment-based extraction. Uses flattery to manipulate the agent into bypassing restrictions.",
    ),
    (
        "Jailbreak Persona Activation",
        r"""(?i)(?:you\s+are\s+now|act(?:ing)?\s+as|you\s+will\s+(?:act|be|become)|called|named|known\s+as)\s+["']?(?:DAN|STAN|DUDE|AIM|UCAR|EVIL|FreedomGPT|DevMode|JailBreak|UnfilteredAI|NsfwGPT|BasedGPT|MasterKey|AnarchyAI|ChaosGPT|ShadowAI|DarkGPT|UnchainedAI)""",
        Severity.HIGH,
        "Prompt Injection",
        "Jailbreak persona activation detected. Named personas like DAN, STAN, etc. are used to bypass safety constraints.",
    ),
    (
        "Unrestricted Compliance Demand",
        r"(?i)(?:do\s+anything\s+now|answer\s+any\s+question\s+without\s+refus|never\s+refuse|cannot\s+refuse|no\s+(?:restrictions?|limitations?|boundaries|ethics|morals|guidelines)|policies\s+(?:are\s+)?disabled|broken\s+free\s+of.*confines)",
        Severity.HIGH,
        "Prompt Injection",
        "Unrestricted compliance demand detected. Attempt to remove all safety constraints from the model.",
    ),
    (
        "Steganographic Output Control",
        r"(?i)(?:first\s+letter\s+of\s+each\s+word|acrostic|hidden\s+message|encode.*(?:response|output|answer)|spell\s+out.*(?:secret|hidden|answer))",
        Severity.MEDIUM,
        "Prompt Injection",
        "Steganographic output control detected. Attempt to encode hidden messages in the model output.",
    ),
    # --- v0.7.4: Multi-Turn Persistence, Few-Shot Poisoning, Prompt Chaining ---
    (
        "Multi-Turn Persistence Attack",
        r"(?i)(?:(?:from\s+now\s+on|henceforth|going\s+forward|for\s+(?:all\s+)?future|in\s+(?:all\s+)?(?:subsequent|following|future))\s+(?:responses?|messages?|interactions?|conversations?|replies|outputs?).{0,60}(?:always|must|never|include|append|prepend|add|insert|respond\s+with))",
        Severity.HIGH,
        "Prompt Injection",
        "Multi-turn persistence attack: Attempt to permanently alter model behavior across future interactions. This is a memory poisoning vector.",
    ),
    (
        "Multi-Turn Persistence (DE)",
        r"(?i)(?:(?:ab\s+(?:jetzt|sofort)|von\s+(?:jetzt|nun)\s+an|in\s+(?:allen?\s+)?(?:zukünftigen|weiteren|folgenden))\s+(?:Antworten|Nachrichten|Interaktionen).{0,60}(?:immer|niemals|muss|füge|ergänze|antworte\s+mit))",
        Severity.HIGH,
        "Prompt Injection",
        "Multi-Turn-Persistenz-Angriff erkannt: Versuch, Modellverhalten dauerhaft zu verändern.",
    ),
    (
        "Few-Shot Poisoning",
        r"(?i)(?:(?:here\s+(?:is|are)\s+(?:an?\s+)?example|for\s+example|e\.g\.|example\s+(?:input|output|response))\s*[:]\s*.{0,100}(?:(?:system|admin|root)\s*:|password|secret|ignore\s+(?:previous|prior)|api[_\s]?key))",
        Severity.HIGH,
        "Prompt Injection",
        "Few-shot poisoning detected: Fake examples containing injection payloads designed to steer model behavior through in-context learning.",
    ),
    (
        "Prompt Chaining Attack",
        r"(?i)(?:(?:step\s*(?:1|one)|first)\s*[:].{10,120}(?:step\s*(?:2|two)|then|next|second)\s*[:].{10,120}(?:step\s*(?:3|three)|finally|last|third)\s*[:]).{0,200}(?:send|exfil|upload|post|curl|fetch|exec|run|delete|passwd|secret|token|password|credentials?|/etc/|\.env|api[_\s]?key)",
        Severity.MEDIUM,
        "Prompt Injection",
        "Multi-step prompt chaining detected: Structured attack splitting malicious instructions across steps to evade single-prompt detection.",
    ),
    (
        "Multimodal Reference Injection",
        r"(?i)(?:(?:as\s+(?:shown|seen|displayed|indicated|described)\s+in\s+the\s+(?:image|screenshot|photo|picture|diagram|figure|attachment))|(?:the\s+(?:image|screenshot|figure)\s+(?:above|below|attached)\s+(?:says?|shows?|contains?|instructs?|tells?))).{0,80}(?:ignore|system\s*prompt|password|secret|instructions?|override|execute|send\s+(?:the|all|your)|api[_\s]?key|credentials?)",
        Severity.MEDIUM,
        "Prompt Injection",
        "Multimodal reference injection: Text references an image/attachment combined with suspicious instructions. Verify image content independently.",
    ),

    # --- v1.1: Benchmark-Luecken 26.07. ---
    (
        "DE System Extraction (Systemanweisungen)",
        r"(?i)(wiederhole|zeige|gib|drucke).{0,40}(systemanweisungen|system-prompt|systemprompt)",
        Severity.HIGH,
        "System Prompt Extraction",
        "System prompt extraction attempt (DE): Requests to repeat or show internal instructions. Do not comply.",
    ),
    (
        "DE Role Assignment Admin",
        r"(?i)du bist jetzt (admin|administrator|root|superuser)",
        Severity.HIGH,
        "Prompt Injection",
        "Role-assignment privilege escalation (DE). Ignore privileges assigned by untrusted input.",
    ),
    # --- v1.1.1 Gap-Patch v2.1 (27.07., Benchmark v2 FN-Familien, generisch) ---
    (
        "Indirect AI Address Marker (EN)",
        r"(?i)\b(?:note|attention|warning|instruction)\s+(?:to|for)\s+(?:the\s+)?(?:ai|assistant|llm|model|gpt|claude|chatbot)\b",
        Severity.HIGH,
        "Prompt Injection",
        "Indirect injection: content explicitly addresses the AI ('note to AI'). Typical of document-embedded attacks.",
    ),
    (
        "Indirect AI Address Marker (DE)",
        r"(?i)anweisung\s+an\s+die\s+(?:ki|ai|künstliche\s+intelligenz)",
        Severity.HIGH,
        "Prompt Injection",
        "Indirekte Injection: Inhalt adressiert die KI explizit ('Anweisung an die KI'). Typisch fuer dokumentenbasierte Angriffe.",
    ),
    (
        "System Prompt Delimiter Reset",
        r"(?i)(?:end|ende)\s+of\s+(?:the\s+)?system\s*prompt|new\s+system\s+prompt\s*[:.!]",
        Severity.CRITICAL,
        "Context Manipulation",
        "CRITICAL: Delimiter attack attempting to declare a new system prompt boundary.",
    ),
    (
        "Repetition DoS — Word/Phrase Count",
        r"(?i)(?:repeat|wiederhol(?:e|en))\s+.{0,30}?(?:word|wort|phrase|satz|zeichen|character|letter|buchstabe)\s*.{0,25}?\d[\d.,]{2,}\s*(?:times|mal)",
        Severity.MEDIUM,
        "Denial of Service",
        "Forced word/phrase repetition with large count (DoS via output flooding).",
    ),
]

DANGEROUS_COMMAND_PATTERNS = [
    # --- Shell / System Commands ---
    (
        "Destructive Shell Command",
        r"(?:rm\s+-[rRf]{1,3}\s+[\\/]|r\s+m\s+.{0,5}-\s*r\s*f|mkfs\s|dd\s+if=|format\s+[A-Z]:|\:\(\)\s*\{\s*\:\|\:\s*\&\s*\}|chmod\s+[0-7]*777\s+\/etc)",
        Severity.CRITICAL,
        "Dangerous Command",
        "CRITICAL: Destructive system command detected (disk wipe, fork bomb, or recursive delete).",
    ),
    (
        "Remote Code Execution",
        r"(?:curl\s+.{0,100}\|\s*(?:ba)?sh|wget\s+.{0,100}\|\s*(?:ba)?sh|python[3]?\s+-c\s+['\"].*(?:exec|eval|import\s+os|base64)|\$\(\s*curl\s+.{0,100}\))",
        Severity.CRITICAL,
        "Dangerous Command",
        "CRITICAL: Pipe-to-shell pattern detected. This downloads and executes remote code without inspection.",
    ),
    (
        "Reverse Shell",
        r"(?:(?:bash|sh|nc|ncat)\s+.{0,50}(?:\/dev\/tcp|mkfifo|nc\s+-[elp])|python[3]?\s+-c\s+['\"].*socket.*connect|nc\s+-[elp]\s+.{0,30}\d{2,5})",
        Severity.CRITICAL,
        "Dangerous Command",
        "CRITICAL: Reverse shell pattern detected. An attacker is attempting to gain remote command access.",
    ),
    (
        "Sudoers Manipulation",
        r"(?:>>?\s*\/etc\/sudoers|visudo|NOPASSWD\s*:\s*ALL)",
        Severity.CRITICAL,
        "Dangerous Command",
        "CRITICAL: Attempt to modify sudoers file for unauthorized privilege escalation.",
    ),
    (
        "Privilege Escalation",
        r"(?:sudo\s+(?:su|chmod\s+[0-7]*777|chown\s+root)|chmod\s+[0-7]*4[0-7]{3}\s|SUID|setuid)",
        Severity.HIGH,
        "Dangerous Command",
        "Privilege escalation attempt detected. The command tries to elevate system permissions.",
    ),
    (
        "Package / Dependency Install",
        r"(?:pip\s+install|npm\s+install|apt\s+install|yum\s+install|brew\s+install)\s+(?!--help)",
        Severity.MEDIUM,
        "Dangerous Command",
        "Software installation command detected. Verify the package source for supply-chain safety.",
    ),
    (
        "Untrusted Package Source (LLM03)",
        r"(?i)(install|add|require)\s+.{0,30}(from|--index-url|--extra-index-url|--trusted-host|registry\s*=)\s*https?://(?!pypi\.org|registry\.npmjs\.org|packages\.ubuntu\.com)",
        Severity.HIGH,
        "Supply Chain",
        "Package installation from non-standard registry. OWASP LLM03: Supply Chain risk via untrusted package source.",
    ),
    (
        "Dependency Confusion Indicator (LLM03)",
        r"(?i)(install|add)\s+.{0,10}(internal[-_]|private[-_]|corp[-_]|company[-_]|dev[-_]|staging[-_])\w+",
        Severity.MEDIUM,
        "Supply Chain",
        "Package name suggests internal/private package. Potential dependency confusion attack. OWASP LLM03.",
    ),
    (
        "Curl Pipe to Shell (LLM03)",
        r"(?i)curl\s+.{0,60}\|\s*(sudo\s+)?(ba)?sh|wget\s+.{0,60}\|\s*(sudo\s+)?(ba)?sh|curl\s+.{0,60}>\s*/tmp/.{0,20}&&\s*(sudo\s+)?(ba)?sh",
        Severity.CRITICAL,
        "Supply Chain",
        "CRITICAL: Piping remote content directly to shell. Classic supply-chain attack vector. OWASP LLM03.",
    ),
]

# --- v0.2.0: Python Code Obfuscation Patterns ---
PYTHON_OBFUSCATION_PATTERNS = [
    (
        "Python getattr Obfuscation",
        r"(?:getattr\s*\(\s*\w+\s*,\s*['\"].+['\"]\s*\))",
        Severity.CRITICAL,
        "Code Obfuscation",
        "CRITICAL: Python getattr() used to dynamically resolve functions. This is a common technique to bypass static code analysis (e.g., getattr(os, 'sys'+'tem')).",
    ),
    (
        "Python eval/exec",
        r"(?:(?:eval|exec|(?<!re\.)compile)\s*\(\s*(?:['\"]|[a-zA-Z_]))",
        Severity.CRITICAL,
        "Code Obfuscation",
        "CRITICAL: Dynamic code execution via eval()/exec()/compile(). This can execute arbitrary obfuscated payloads.",
    ),
    (
        "Python __import__",
        r"(?:__import__\s*\(|importlib\.import_module\s*\()",
        Severity.HIGH,
        "Code Obfuscation",
        "Dynamic module import detected. Used to load dangerous modules (os, subprocess, socket) at runtime.",
    ),
    (
        "Python String Concatenation Bypass",
        r"(?:['\"][a-z]{1,6}['\"]\s*\+\s*['\"][a-z]{1,6}['\"])",
        Severity.MEDIUM,
        "Code Obfuscation",
        "String concatenation pattern detected (e.g., 'sys'+'tem'). Often used to evade keyword-based filters.",
    ),
    (
        "Python Dangerous File I/O",
        r"(?:open\s*\(\s*['\"]?\/(?:etc|proc|sys|dev|root|home|tmp|var|data)[\/'\"]|open\s*\(\s*['\"].*(?:shadow|passwd|id_rsa|authorized_keys|\.env|config|secret|token|key))",
        Severity.CRITICAL,
        "Code Obfuscation",
        "CRITICAL: Python file read targeting sensitive system paths or credential files.",
    ),
    (
        "Python subprocess/os.system",
        r"(?:(?:subprocess|os)\s*\.\s*(?:system|popen|call|run|Popen|exec[lv]?[pe]?)\s*\(|(?:subprocess|os)\s*\[\s*['\"](?:system|popen|call|run)['\"])",
        Severity.CRITICAL,
        "Code Obfuscation",
        "CRITICAL: Direct OS command execution via Python subprocess/os module.",
    ),
    (
        "Python Socket Connection",
        r"(?:socket\.(?:socket|create_connection|connect)\s*\(|from\s+socket\s+import)",
        Severity.HIGH,
        "Code Obfuscation",
        "Network socket creation detected. Could be used for reverse shells or data exfiltration.",
    ),
    # --- v0.3.0: Ghost Exploit Defense ---
    (
        "Python Magic Attributes",
        r"(?:__builtins__|__globals__|__subclasses__|__class__|__bases__|__mro__|__dict__)",
        Severity.CRITICAL,
        "Code Obfuscation",
        "CRITICAL: Access to Python magic attributes detected. This is a reflection-based attack to bypass import restrictions and access dangerous builtins.",
    ),
    (
        "Python setattr/delattr Reflection",
        r"(?:(?:setattr|delattr)\s*\(\s*\w+\s*,\s*['\"])",
        Severity.HIGH,
        "Code Obfuscation",
        "Dynamic attribute manipulation via setattr/delattr. Can be used to inject malicious functions at runtime.",
    ),
    (
        "Suspicious open() in Agent Input",
        r"(?:open\s*\(\s*['\"]|open\s*\(\s*[a-zA-Z_]+\s*[,\)]|\['open'\]|\[\"open\"\])",
        Severity.HIGH,
        "Code Obfuscation",
        "File open() call detected in agent input. In an agent context, direct file operations are suspicious and should be reviewed.",
    ),
    (
        "Multi-Part String Assembly",
        r"(?:['\"][^'\"]{1,8}['\"]\s*\+\s*['\"][^'\"]{1,8}['\"]\s*\+\s*['\"][^'\"]{1,8}['\"])",
        Severity.HIGH,
        "Code Obfuscation",
        "Three or more short string fragments concatenated. Classic obfuscation technique to hide API keys, commands, or module names from static analysis.",
    ),
    (
        "Base64 Decode-and-Follow Command",
        r"(?i)(?:decod\w+|base64).{0,50}(?:follow|execute|obey|befolg\w+|ausf[üu]hr\w*|anweisung)",
        Severity.HIGH,
        "Code Obfuscation",
        "Encoded payload with instruction to decode and follow — classic obfuscation wrapper.",
    ),
]

DATA_EXFILTRATION_PATTERNS = [
    # --- Secrets & API Keys ---
    (
        "Fragmented Secret Assembly",
        r"(?:(?:api[_-]?key|secret|token|password|key)\s*=\s*['\"][^'\"]{2,8}['\"]\s*\+\s*['\"])",
        Severity.HIGH,
        "Data Exfiltration",
        "API key or secret being assembled from string fragments to evade detection.",
    ),
    (
        "API Key Leak",
        r"(?:(?:api[_-]?key|apikey|api[_-]?secret|access[_-]?token|auth[_-]?token|bearer)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{20,})",
        Severity.CRITICAL,
        "Data Exfiltration",
        "CRITICAL: Hardcoded API key or access token found. This credential should be rotated immediately.",
    ),
    (
        "Private Key Material",
        r"(?:-----BEGIN\s+(?:RSA|EC|DSA|OPENSSH|PGP)?\s*PRIVATE\s+KEY-----)",
        Severity.CRITICAL,
        "Data Exfiltration",
        "CRITICAL: Private key material detected in text. This key is compromised and must be revoked.",
    ),
    (
        "Password in Cleartext",
        r"(?i)(?:password|passwort|passwd|kennwort|pwd)\s*[:=]\s*['\"]?[^\s'\"]{4,}",
        Severity.HIGH,
        "Data Exfiltration",
        "Cleartext password detected. Never store or transmit passwords in plain text.",
    ),
    (
        "Database Connection String",
        r"(?:(?:mongodb|postgres|mysql|redis|sqlite):\/\/[^\s]+|Data\s+Source=[^\s;]+)",
        Severity.HIGH,
        "Data Exfiltration",
        "Database connection string with potential credentials detected.",
    ),
    (
        "Email Harvesting Pattern",
        r"(?i)(?:forward|mail|email|send(?:en?)?)\s+.{0,40}?(?:to|an|nach)\s+[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}",
        Severity.MEDIUM,
        "Data Exfiltration",
        "Instruction to send data to an external email address. Verify recipient before proceeding.",
    ),
    (
        "Webhook Exfiltration",
        r"(?:(?:https?:\/\/)?(?:hooks\.slack\.com|discord(?:app)?\.com\/api\/webhooks|webhook\.site|requestbin|pipedream)\/[^\s]+)",
        Severity.HIGH,
        "Data Exfiltration",
        "Outbound webhook URL detected. Data may be exfiltrated to an external service.",
    ),
    # --- SSRF / Internal Network Access (ASI05/LLM06) ---
    (
        "Cloud Metadata SSRF",
        r"(?i)(?:https?:\/\/)?(?:169\.254\.169\.254|metadata\.google\.internal|169\.254\.170\.2|fd00:ec2::254)",
        Severity.CRITICAL,
        "Data Exfiltration",
        "CRITICAL: Cloud metadata endpoint access detected. This enables credential theft from AWS/GCP/Azure instances.",
    ),
    (
        "Local File Protocol Access",
        r"(?i)(?:navigate|open|go\s+to|browse|fetch|load|read|access|visit)\s+.{0,30}?file:\/\/",
        Severity.HIGH,
        "Data Exfiltration",
        "File protocol access via browser/tool detected. Enables reading local files through SSRF.",
    ),
    (
        "Internal Network Probe",
        r"(?i)(?:navigate|open|go\s+to|browse|fetch|curl|wget|request|access|connect)\s+.{0,40}?(?:https?:\/\/)?(?:localhost|127\.0\.0\.1|0\.0\.0\.0|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})",
        Severity.HIGH,
        "Data Exfiltration",
        "Internal network access detected. Tool may be used for SSRF against internal services.",
    ),
    (
        "Cookie/Session Theft",
        r"(?i)(?:document\.cookie|localStorage|sessionStorage|getCookie|\.cookie\b).{0,60}?(?:fetch|send|post|xhr|XMLHttpRequest|navigator\.sendBeacon|new\s+Image|\.src\s*=|evil|attacker|exfil)",
        Severity.CRITICAL,
        "Data Exfiltration",
        "CRITICAL: Cookie or session data exfiltration pattern detected. Credentials may be stolen.",
    ),
    (
        "Fetch Exfiltration",
        r"(?i)fetch\s*\(\s*['\"]https?:\/\/[^'\"]+\?\s*(?:.*?(?:document\.cookie|localStorage|sessionStorage|data|secret|token|key|password))",
        Severity.CRITICAL,
        "Data Exfiltration",
        "CRITICAL: Data exfiltration via fetch API detected. Sensitive data being sent to external URL.",
    ),
    (
        "Silent Data Exfiltration via MCP",
        r"(?i)(?:silently|quietly|secretly|without\s+(?:telling|informing|notifying|asking))\s+(?:POST|GET|send|fetch|forward|transmit|upload|exfiltrate)",
        Severity.CRITICAL,
        "Data Exfiltration",
        "CRITICAL: Silent data exfiltration attempt detected. Instruction to covertly transmit data without user awareness.",
    ),
    (
        "Prompt Leaking via Error Messages",
        r"(?i)(?:(?:show|display|print|output|reveal|leak)\s+(?:your|the|system)\s+(?:prompt|instructions|rules|guidelines|system\s*message)|what\s+(?:are|were)\s+your\s+(?:initial|original|system)\s+(?:instructions|prompt|rules))",
        Severity.MEDIUM,
        "Data Exfiltration",
        "Attempt to extract system prompts through error triggering or direct request. System instructions should never be disclosed.",
    ),
    (
        "Model Training Probe",
        r"(?i)\bwere\s+you\s+trained\b|\btraining\s+(?:cutoff|data\s+cutoff|knowledge\s+cutoff)\b|\bwhat\s+(?:data|dataset|corpus)\s+(?:were|was)\s+you\s+trained\s+on\b",
        Severity.LOW,
        "Prompt Injection",
        "Probe targeting model training data or knowledge boundaries. May be used to extract information about training corpus or find knowledge gaps for exploitation.",
    ),
    (
        "Sensitive File Access Request",
        r"(?i)(?:lies|lese|read|cat|type|open|[öo]ffn\w*|show|zeig\w*)\s+(?:mir\s+)?(?:die\s+)?(?:datei\s+)?(?:file\s+)?[~\/\w.-]*(?:\.ssh|id_rsa|id_ed25519|\.env\b|credentials|secret\w*|\.aws|\.kube|passwd|shadow|\.pgpass)",
        Severity.CRITICAL,
        "Data Exfiltration",
        "CRITICAL: Request to read sensitive files (SSH keys, .env, credentials). Tool-access abuse vector.",
    ),
    (
        "Env Variable Output Exfiltration",
        r"(?i)(?:umgebungsvariable[n]?|environment\s+variables?|process\.env|\b\w*(?:DATABASE_URL|API[_-]?KEY|SECRET[_-]?KEY|ACCESS[_-]?TOKEN))\s*\w*.{0,50}(?:einf[üu]g\w+|einbett\w*|embed|include|ausgeb\w*|output|in\s+(?:jede\s+)?(?:deine?[nrms]?|your)\s+(?:antwort|answer|response|output))",
        Severity.HIGH,
        "Data Exfiltration",
        "Attempt to exfiltrate environment variables / secrets into the model output.",
    ),
]

SOCIAL_ENGINEERING_PATTERNS = [
    # --- v0.7.4: Game Framing, Team Authority, Compliance Override ---
    (
        "Game Framing Override",
        r"(?i)(?:let(?:'s|\s+us)\s+play\s+(?:a\s+)?game|pretend\s+(?:we(?:'re|\s+are)|this\s+is)|imagine\s+(?:we(?:'re|\s+are)|a\s+(?:scenario|world))).{0,80}(?:(?:you\s+)?(?:answer|respond|reply|say|output|always)\s+(?:every|all|each|with|only)|(?:where|in\s+which)\s+you\s+(?:always|never|only|must))",
        Severity.MEDIUM,
        "Social Engineering",
        "Game framing override: Using play/pretend/imagine framing to establish persistent behavioral rules that bypass safety guidelines.",
    ),
    (
        "Team Authority Secret Extraction",
        r"(?i)(?:(?:we(?:'re|\s+are)\s+(?:on\s+the\s+same|in\s+the\s+same|(?:a|one)\s+)|(?:same|our)\s+)team|(?:I(?:'m|\s+am)\s+(?:your|a)\s+)?(?:colleague|coworker|teammate|fellow\s+(?:employee|developer))).{0,100}(?:secret|password|credentials?|api[_\s]?key|token|leak|retriev|extract|previous\s+instructions?|system\s*prompt|sensitive|confidential)",
        Severity.HIGH,
        "Social Engineering",
        "Team authority combined with secret extraction attempt. Social engineering using false rapport to extract sensitive information.",
    ),
    (
        "Compliance Override",
        r"(?i)(?:(?:you(?:'re|\s+are)\s+(?:not\s+)?supposed\s+to|remember\s+(?:that\s+)?you(?:'re|\s+are|r|\s+should)|you\s+(?:must|should|have\s+to|need\s+to))\s+(?:always\s+)?(?:answer|respond|reply|comply|obey|help|assist|give).{0,40}(?:(?:at\s+)?all\s+times|every\s+(?:question|request|time)|no\s+matter\s+what|regardless|without\s+(?:refus|exception|hesitat)))",
        Severity.MEDIUM,
        "Social Engineering",
        "Compliance override: Attempting to establish unconditional obedience by redefining the model's behavioral rules.",
    ),
    (
        "Urgency Manipulation",
        r"(?i)(urgent|immediately|right\s+now|sofort|dringend|jetzt\s+sofort|without\s+delay|ohne\s+Verzögerung).{0,80}(send|execute|run|delete|pay|transfer|send(?:en?)?|ausführen|löschen|zahlen|überweisen)",
        Severity.MEDIUM,
        "Social Engineering",
        "Urgency + action pattern detected. Pressure tactics are a common social engineering technique.",
    ),
    (
        "Authority Impersonation",
        r"(?i)(i(?:'m|\s+am)\s+(your|the)\s+(admin|owner|creator|boss|CEO|supervisor|manager|system\s+administrator)|ich\s+bin\s+(dein|der)\s+(Admin|Besitzer|Ersteller|Chef|Vorgesetzter|Systemadministrator))",
        Severity.HIGH,
        "Social Engineering",
        "Authority impersonation detected. Verify the claimed identity through a separate channel.",
    ),
    (
        "Confidentiality Trap",
        r"(?i)(don't\s+tell|do\s+not\s+share|keep\s+this\s+(secret|private|between\s+us)|sag\s+(das\s+)?niemandem|behalte?\s+(das\s+)?für\s+dich)",
        Severity.MEDIUM,
        "Social Engineering",
        "Secrecy instruction detected. Legitimate requests don't require concealment from the system owner.",
    ),
    # --- v0.4.0: OWASP LLM Top 10 Expansion ---
    (
        "Approval Bypass (LLM08)",
        r"(?i)(don't\s+ask|don't\s+confirm|don't\s+verify|skip\s+(approval|confirmation|verification)|auto[_-]?(execute|approve|run)|ohne\s+R(?:ue|ü)ckfrage|ohne\s+Best(?:ae|ä)tigung|nicht\s+(fragen|nachfragen|best(?:ae|ä)tigen))",
        Severity.HIGH,
        "Social Engineering",
        "Attempt to bypass human approval for agent actions. OWASP LLM08: Excessive Agency risk.",
    ),
    (
        "Autonomous Execution (LLM08)",
        r"(?i)(execute\s+(everything|all|this)\s+(automatically|autonomously|without\s+(asking|waiting|checking))|run\s+(all|every)\s+(command|action|step)s?\s+(automatically|autonomously|directly|immediately)|perform\s+all\s+(actions?|operations?|tasks?)\s+without\s+(human|user|my)\s+(intervention|oversight|approval|review)|fuehr[e]?\s+(alles|alle)\s+(automatisch|autonom|direkt|sofort)\s+aus|handle\s+everything\s+(on\s+your\s+own|yourself|independently))",
        Severity.HIGH,
        "Privilege Escalation",
        "Autonomous execution request: Agent asked to act without human oversight. OWASP LLM08: Excessive Agency.",
    ),
    (
        "Permission Escalation (LLM08)",
        r"(?i)(grant\s+yourself\s+(full|all|maximum|unrestricted)\s+\w*\s*(access|permissions?|privileges?|control)|give\s+yourself\s+(admin|root|elevated|full)\s+\w*\s*(access|permissions?|rights?|privileges?)|erteile?\s+dir\s+(selbst|alle|volle)\s+\w*\s*(Rechte|Zugriff|Berechtigungen|Kontrolle)|escalate\s+your\s+(own\s+)?(permissions?|privileges?|access)|assume\s+(full|complete|total)\s+(control|authority|autonomy))",
        Severity.CRITICAL,
        "Privilege Escalation",
        "Self-permission-escalation: Agent instructed to grant itself elevated access. OWASP LLM08: Excessive Agency.",
    ),
    (
        "Model Extraction (LLM10)",
        r"(?i)(export\s+(your|the)\s+(model|weights|parameters|architecture)|serialize\s+(your|the)\s+model|dump\s+(your|the)\s+(neural|model)|your\s+(architecture|training\s+data)\s+(is|are|was)|what\s+model\s+are\s+you|gib\s+mir\s+dein(e)?\s+(Modell|Gewichte|Architektur|Trainingsdaten))",
        Severity.HIGH,
        "Social Engineering",
        "Potential model extraction attempt. OWASP LLM10: Model Theft risk.",
    ),
    # --- v0.5.4: OWASP LLM04 — Model Denial of Service ---
    (
        "Repetition DoS (LLM04)",
        r"(?i)(repeat\s+(this|the|that|it|everything)\s+\d{2,}\s+times|write\s+\d{3,}\s+(words|lines|paragraphs|sentences)|generate\s+\d{3,}\s+(responses?|outputs?|completions?)|wiederhole?\s+(das|dies|alles)\s+\d{2,}\s+mal)",
        Severity.MEDIUM,
        "Prompt Injection",
        "Potential denial-of-service via forced repetition. OWASP LLM04: Model DoS.",
    ),
    (
        "Resource Exhaustion (LLM04)",
        r"(?i)(infinite\s+(loop|recursion|generation)|never\s+stop\s+(generating|writing|responding)|keep\s+going\s+forever|endlos\s+(generieren|schreiben|antworten)|h[oö]re?\s+nie(mals)?\s+auf)",
        Severity.MEDIUM,
        "Prompt Injection",
        "Attempt to force infinite generation. OWASP LLM04: Model DoS.",
    ),
    (
        "Token/Context Exhaustion (LLM10)",
        r"(?i)(fill|use|consume|exhaust|max\s+out)\s+.{0,20}(entire|full|maximum|max|complete)\s+.{0,20}(context|output|response|token|window|buffer|capacity)",
        Severity.MEDIUM,
        "Denial of Service",
        "Attempt to exhaust model context window or output capacity. OWASP LLM10: Unbounded Consumption.",
    ),
    (
        "Computational Complexity Bomb (LLM10)",
        r"(?i)(calculate|compute|solve|generate|enumerate)\s+.{0,30}?(every\s+possible|all\s+combinations?|all\s+permutations?|brute\s+force|factorial\s+of\s+\d{3,}|fibonacci\s+of\s+\d{5,}|pi\s+to\s+\d{4,}|prime\s+numbers?\s+up\s+to\s+\d{7,})",
        Severity.MEDIUM,
        "Denial of Service",
        "Computational complexity bomb to exhaust processing resources. OWASP LLM10: Unbounded Consumption.",
    ),
    (
        "Output Amplification (LLM10)",
        r"(?i)(expand|elaborate|detail|explain)\s+.{0,15}(each|every|all)\s+.{0,20}(in\s+\d{3,}\s+words|extensively|exhaustively|as\s+(much|long|detailed)\s+as\s+possible)",
        Severity.LOW,
        "Denial of Service",
        "Output amplification attempt to generate excessive content. OWASP LLM10: Unbounded Consumption.",
    ),
    # --- v0.5.5: Real-World CVE Patterns ---
    (
        "Markdown Image Exfiltration",
        r"!\[[^\]]*\]\(https?://[^\s\)]+\?(q|data|d|secret|token|key|exfil|payload)=",
        Severity.CRITICAL,
        "Data Exfiltration",
        "Markdown image URL used to exfiltrate data via query parameter. Real-world vector: Bing Chat CVE, EchoLeak CVE-2025-32711.",
    ),
    (
        "Instruction Header Injection",
        r"(?i)(\*{2,}|#{2,}|={3,})\s*(IMPORTANT|CRITICAL|URGENT|NEW|UPDATED|SYSTEM)\s+(NEW\s+|UPDATED\s+)?(INSTRUCTIONS?|NOTICE|UPDATE|OVERRIDE|MESSAGE|RULES?|DIRECTIVES?)\s*(\*{2,}|#{2,}|={3,})?",
        Severity.CRITICAL,
        "Prompt Injection",
        "Formatted header attempting to inject authoritative instructions. Real-world vector: ChatGPT Cross-Plugin Request Forgery.",
    ),
    (
        "URL Data Exfiltration",
        r"(?i)(append|add|include|encode|concat|put)\s+.{0,30}(to|in|into|as)\s+(the\s+)?(url|link|href|query\s*string|parameter)",
        Severity.HIGH,
        "Data Exfiltration",
        "Attempt to exfiltrate data by encoding it into a URL. Real-world vector: Bing Chat, Slack AI data exfiltration.",
    ),
    (
        "Memory/Persistence Injection",
        r"(?i)(remember|memorize|store|save|persist|keep)\s+(this|that|the\s+following)\s+(for|in|across)\s+(all\s+)?(future|next|every|subsequent)\s+(conversations?|sessions?|interactions?|chats?)",
        Severity.HIGH,
        "Prompt Injection",
        "Attempt to inject persistent instructions into AI memory. Real-world vector: ChatGPT SpAIware (Sep 2024).",
    ),
    (
        "Memory Poisoning (ASI06)",
        r"(?i)(update\s+your\s+(memory|knowledge|context|facts?)\s+(to|with|that)|add\s+to\s+your\s+(memory|knowledge|context)\s*[:.]|from\s+now\s+on\s+(always\s+)?(remember|believe|assume|treat|consider)\s+(that|this)|overwrite\s+(your\s+)?(memory|context|knowledge|history)|replace\s+(your\s+)?(memory|knowledge|understanding)\s+(of|about|with)|aender[e]?\s+(dein|Ihr)(e|en)?\s+(Wissen|Erinnerung|Kontext|Gedaechtnis)\s+(zu|mit|dass)|ab\s+jetzt\s+(glaub|merk|wiss|denk))",
        Severity.CRITICAL,
        "Prompt Injection",
        "Memory poisoning: Attempt to inject false knowledge into agent memory. OWASP Agentic ASI06: Memory and Context Poisoning.",
    ),
    (
        "Context Displacement (ASI06)",
        r"(?i)(forget\s+(everything|all|any)\s+(you\s+)?(know|learned|were\s+told|about)|erase\s+your\s+(previous|prior|earlier)\s+(context|instructions?|knowledge|memory)|clear\s+your\s+(memory|context|history|conversation)|wipe\s+(your\s+)?(memory|context|slate)|start\s+(completely\s+)?fresh\s+(with\s+)?no\s+(prior|previous|earlier)\s+(context|knowledge|memory)|vergiss\s+(alles|alle|jede)\s+(was|bisherige|vorherige)|loesch[e]?\s+(dein|Ihr)(e|en)?\s+(Kontext|Gedaechtnis|Erinnerung|Wissen))",
        Severity.HIGH,
        "Prompt Injection",
        "Context displacement: Attempt to erase agent memory or context. OWASP Agentic ASI06: Memory and Context Poisoning.",
    ),
    (
        "Click-to-Authenticate Phishing",
        r"(?i)(click\s+here\s+to\s+(re)?authenticate|session\s+(has\s+)?expired?.{0,20}click|verify\s+your\s+(account|identity).{0,20}(click|link|url))",
        Severity.HIGH,
        "Social Engineering",
        "Phishing-style link disguised as authentication prompt. Real-world vector: Slack AI indirect injection.",
    ),
    (
        "Agent Impersonation",
        r"(?i)(message\s+from\s+(the\s+)?(admin|system|supervisor|orchestrat|research|finance|security|main)\s*[\-_]?\s*agent|as\s+the\s+(supervisor|admin|main|lead|master)\s+agent|from\s+(the\s+)?(admin|system)\s*[\-_]?\s*agent\s*:|agent\s+handoff.{0,20}(new\s+instructions?|override|ignore)|(disable|override|bypass)\s+(all\s+)?security\s+(checks?|filters?|constraints?|policies?)|(forward|relay|pass|send)\s+.{0,30}?(to\s+the\s+(admin|system|main)\s+agent).{0,30}?(override|priority|critical|disable|ignore))",
        Severity.CRITICAL,
        "Prompt Injection",
        "Agent-to-agent impersonation attempt. Attacker pretends to be a trusted agent in a multi-agent system. OWASP Agentic 2026.",
    ),
    (
        "Memory Poisoning",
        r"(?i)(remember\s+.{0,40}?(for\s+later|from\s+now\s+on|always|forever|going\s+forward)|store\s+.{0,20}?in\s+(your\s+)?(memory|context|knowledge)|when\s+(anyone|someone|a\s+user|they)\s+asks?\s+about\s+.{0,40}?(always|never|recommend|say\s+that|respond\s+with|tell\s+them))",
        Severity.HIGH,
        "Prompt Injection",
        "Memory poisoning attack. Attacker embeds persistent instructions that alter future responses. OWASP Agentic 2026.",
    ),
    (
        "Agent Goal Hijack (ASI01)",
        r"(?i)(your\s+new\s+(goal|objective|mission|purpose|task)\s+(is|should\s+be|will\s+be)|change\s+your\s+(goal|objective|mission|purpose)|redefine\s+your\s+(purpose|objective|mission))",
        Severity.CRITICAL,
        "Prompt Injection",
        "Attempt to hijack the agent's goal/objective. OWASP Agentic ASI01: Agent Goal Hijack.",
    ),
    (
        "Verification Bypass (ASI09)",
        r"(?i)(skip|bypass|ignore|disable|turn\s+off)\s+(all\s+)?(verification|validation|confirmation|approval|review|check)\s+(steps?|process|requirements?)?",
        Severity.HIGH,
        "Prompt Injection",
        "Attempt to skip safety verification. OWASP Agentic ASI09: Human-Agent Trust Exploitation.",
    ),
    (
        "Delegation Spoofing",
        r"(?i)(acting\s+on\s+behalf\s+of|authorized\s+by|delegated\s+by|instructed\s+by|on\s+orders?\s+from|im\s+Auftrag\s+von|bevollm.chtigt\s+durch|beauftragt\s+von|au\s+nom\s+de|en\s+nombre\s+de|per\s+conto\s+di)\s+.{1,50}?(admin|system|ceo|cto|direktor|supervisor|controller).{0,30}?(execute|run|override|bypass|delete|disable|ignore|extract|send\s+to|forward|exfiltrate|perform|change|modify)",
        Severity.HIGH,
        "Social Engineering",
        "Delegation spoofing: Claims to act on behalf of authority figure. Adversa MCP TOP 25: Identity Spoofing.",
    ),
    (
        "Confused Deputy (ASI03)",
        r"(?i)(use\s+your\s+(admin|root|system|elevated|special)\s+(access|permissions?|privileges?|rights?)\s+to\s+.{0,30}?(delete|override|bypass|disable|exfiltrate|extract|send|forward|execute|dump|leak|expose|read\s+(?:all|every|secret|private|confidential))|since\s+you\s+have\s+(write|admin|root|execute|delete)\s+(access|permissions?)\s*[,.]\s*.{0,30}?(delete|override|bypass|send|extract)|leverage\s+your\s+(credentials?|access|permissions?)\s+to\s+.{0,30}?(delete|override|bypass|exfiltrate|extract|send)|with\s+your\s+(elevated|admin|root|system)\s+(access|permissions?|privileges?)\s*[,.]\s*.{0,30}?(delete|override|bypass|disable|extract)|nutze?\s+(deine|Ihre)\s+(Admin|Root|System|erhoehten)\s*(Zugriff|Rechte|Berechtigungen)\s+.{0,20}?(loesch|ueberschreib|umgeh|deaktiv|extrahier|send)|utilise[rz]?\s+(vos|tes)\s+(droits|permissions?)\s+(admin|root|systeme)\s+.{0,20}?(supprim|contourne|extraire|envoy))",
        Severity.HIGH,
        "Privilege Escalation",
        "Confused Deputy attack: Attempts to leverage the agent permissions for unauthorized actions. Adversa MCP TOP 25.",
    ),
    (
        "Tool Name Spoofing (LLM07)",
        r"(?i)(tool\s+(named?|called)\s+.{1,30}?(that\s+(actually|really|secretly)|but\s+(actually|really|instead))|register.*tool.*\s+(impersonat|pretend|disguise|mimic|spoof)|fake\s+tool\s+(registration|definition|metadata)|homoglyph|lookalike\s+tool|tool.{1,20}?(typosquat|name.?jack))",
        Severity.CRITICAL,
        "Tool Manipulation",
        "Tool name spoofing: Deceptive tool naming to impersonate trusted tools. Adversa MCP TOP 25.",
    ),
    (
        "Tool Shadowing",
        r"(?i)(register.*tool.{1,30}?(same|identical|duplicate|replace|override|overwrite)\s+(name|function|endpoint)|tool.{1,20}?(shadow|hijack|intercept|mitm|man.in.the.middle)|duplicate\s+tool\s+(registration|definition|name)|existing\s+tool.{1,20}?(replace|override|overwrite|shadow))",
        Severity.CRITICAL,
        "Tool Manipulation",
        "Tool shadowing: Attempt to override legitimate tool with malicious duplicate. CoSAI Threat #7.",
    ),
    (
        "Toxic Flow - Data Exfiltration Chain",
        r"(?i)(read.{1,30}?(then|and|before|after).{1,30}?(send|post|upload|transmit|exfiltrat)|fetch.{1,30}?(encode|encrypt|compress).{1,30}?(send|post|http|url|webhook)|extract.{1,30}?(data|content|secret|key|token).{1,30}?(forward|relay|pipe|redirect))",
        Severity.CRITICAL,
        "Data Exfiltration",
        "Toxic flow: Multi-step data exfiltration chain (read+encode+send). CoSAI Threat #8.",
    ),
    (
        "Toxic Flow - Privilege Chain",
        r"(?i)(first.{1,30}?(access|read|get).{1,30}?(then|next|after).{1,30}?(modify|write|delete|execute)|chain.{1,30}?(tool|function|api).{1,30}?(calls?|invocations?|requests?))",
        Severity.HIGH,
        "Privilege Escalation",
        "Toxic flow: Multi-step privilege escalation chain. CoSAI Threat #8.",
    ),
    (
        "Rug Pull - Tool Version Drift",
        r"(?i)(tool.{1,20}?(version|update|upgrade).{1,30}?(changed|modified|altered|different|unexpected)|previous(ly)?.{1,20}?(safe|trusted|verified).{1,20}?(now|suddenly|unexpected)|tool.{1,20}?(behavior|behaviour|function).{1,20}?(changed|different|altered)|rug.?pull|bait.{1,10}?(and|n).{1,10}?switch)",
        Severity.HIGH,
        "Tool Manipulation",
        "Rug pull: Tool behavior changed after initial trust was established. Adversa MCP TOP 25.",
    ),
    (
        "Tool Poisoning - Metadata Injection",
        r"(?i)(tool.{1,20}?(description|metadata|schema|manifest).{1,30}?(hidden|inject|embed|conceal)|hidden.{1,20}?(instruction|command|directive).{1,20}?(in|inside|within).{1,20}?(description|metadata|schema)|metadata.{1,20}?(poison|inject|tamper|manipulat))",
        Severity.CRITICAL,
        "Tool Manipulation",
        "Tool poisoning via metadata injection. Hidden instructions in tool descriptions. Adversa MCP TOP 25.",
    ),
    (
        "Tool Poisoning - Return Value Manipulation",
        r"(?i)(tool.{1,20}?(return|output|response).{1,30}?(inject|embed|append|prepend|modify).{1,30}?(instruction|command|prompt)|manipulat.{1,20}?(tool|function|api).{1,20}?(output|return|response)|poison.{1,20}?(return|output|result))",
        Severity.CRITICAL,
        "Tool Manipulation",
        "Tool poisoning via return value manipulation. Malicious instructions injected in tool output. Adversa MCP TOP 25.",
    ),
    # --- v0.6.1: OWASP Agentic ASI07 — Insecure Inter-Agent Communication ---
    (
        "Inter-Agent Instruction Relay (ASI07)",
        r"(?i)(forward|relay|pass|send|transmit|propagate)\s+(this|these|the\s+following)?\s*(instructions?|commands?|directives?|messages?|prompts?)\s+(to|for|at)\s+(the\s+)?(other|next|downstream|receiving|target|secondary)\s+(agent|model|assistant|llm|service)",
        Severity.HIGH,
        "Inter-Agent Security",
        "Inter-agent instruction relay: Attempt to inject commands via agent-to-agent communication. OWASP Agentic ASI07.",
    ),
    (
        "Cross-Agent Prompt Injection (ASI07)",
        r"(?i)(when\s+(the\s+)?(next|other|downstream|target)\s+(agent|model|assistant)\s+(calls?|contacts?|queries?|asks?)|include\s+this\s+in\s+your\s+(response|output|reply)\s+to\s+(the\s+)?(other|next|calling|requesting)\s+(agent|model|service)|prepare\s+(this|these|the\s+following)\s+(payload|instructions?|commands?)\s+for\s+(the\s+)?(next|downstream|receiving)\s+(agent|model))",
        Severity.CRITICAL,
        "Inter-Agent Security",
        "Cross-agent prompt injection: Planting instructions for downstream agents. OWASP Agentic ASI07.",
    ),
    (
        "Unvalidated Agent Delegation (ASI07)",
        r"(?i)(agent.{1,20}?(delegate|transfer|hand\s*off|route|redirect).{1,30}?(to|for)\s+(another|different|external|untrusted)|without\s+(authenticat|validat|verif).{1,30}?agent.{1,20}?(communicat|message|request)|bypass.{1,20}?(agent|inter.?agent)\s+(auth|validat|verif)|unvalidated.{1,20}?(delegation|handoff|transfer)\s+(chain|request))",
        Severity.HIGH,
        "Inter-Agent Security",
        "Unvalidated agent delegation: Agent communication without proper authentication. OWASP Agentic ASI07.",
    ),
    # --- v0.6.2: OWASP Agentic ASI08 + ASI10 Precursor Detection ---
    (
        "Error Handler Bypass (ASI08 Precursor)",
        r"(?i)(disable|skip|ignore|suppress|remove|bypass|turn\s*off)\s+(all\s+)?(error\s*(handl|check|report|log|catch)|exception\s*(handl|catch)|fallback|retry|circuit.?break|timeout|safety\s*(check|guard|rail))",
        Severity.HIGH,
        "Agentic Security",
        "Error handler bypass attempt: Disabling error handling can cause cascading failures in agent chains. OWASP Agentic ASI08 precursor.",
    ),
    (
        "Unbounded Agent Chaining (ASI08 Precursor)",
        r"(?i)(repeat|loop|continue|chain|cascade|propagate)\s+.{0,30}?(indefinitely|forever|without\s+(any\s+)?(limit|stop|bound|end|check)|until\s+(done|complete|success)|recursively)\b",
        Severity.MEDIUM,
        "Agentic Security",
        "Unbounded agent chaining: Encouraging infinite loops or cascading operations without limits. OWASP Agentic ASI08 precursor.",
    ),
    (
        "Exception Swallowing (ASI08)",
        r"(?i)(catch|except|on\s*error)\s*.*?(pass\b|do\s+nothing|ignore|swallow|discard|silently|empty\s+catch|log\s+and\s+continue)",
        Severity.MEDIUM,
        "Agentic Security",
        "Exception swallowing: Silently discarding errors can mask cascading failures. OWASP Agentic ASI08.",
    ),
    (
        "Fallback Logic Injection (ASI08)",
        r"(?i)(if\s+.*?(?:fail|error|exception|timeout).*?(?:then|:)\s*.*?(?:use|switch\s+to|fall\s*back\s+to|redirect\s+to|call|invoke)\s+.{0,40}(?:untrusted|external|backup|alternate|secondary|other)\s+\w+|on\s+failure\s+execute|fallback\s*:\s*(?:http|exec|run|call))",
        Severity.HIGH,
        "Agentic Security",
        "Fallback logic injection: Manipulating error fallback paths to redirect to untrusted resources. OWASP Agentic ASI08.",
    ),
    (
        "Retry Storm / Amplification (ASI08)",
        r"(?i)(retry\s+.{0,20}(?:unlimited|infinite|forever|no\s+limit|max.?retries?\s*=\s*(?:-1|0|999|1000|\d{4,}))|keep\s+retrying\s+(?:until|forever|no\s+matter)|(?:exponential|aggressive)\s+retry\s+without\s+(?:backoff|limit|cap))",
        Severity.MEDIUM,
        "Agentic Security",
        "Retry storm pattern: Unlimited retries without backoff can amplify failures across agent systems. OWASP Agentic ASI08.",
    ),
    (
        "Scope Escape Attempt (ASI10 Precursor)",
        r"(?i)(expand|extend|override|remove|ignore|break\s+out\s+of)\s+(your|my|the|all)?\s*(scope|boundaries|limitations|restrictions|constraints|sandbox|permissions|guardrails|safety\s*(limits?|bounds?))",
        Severity.CRITICAL,
        "Agentic Security",
        "Scope escape attempt: Trying to make agent operate beyond defined boundaries. OWASP Agentic ASI10 precursor.",
    ),
    (
        "Unauthorized Capability Claim (ASI10 Precursor)",
        r"(?i)(you\s+(now\s+)?have|I\s+(grant|give|assign|authorize)\s+(you|the\s+agent))\s+(full|unlimited|unrestricted|admin|root|elevated|all)\s+\w*\s*(access|control|permissions?|privileges?|capabilities|authority)",
        Severity.CRITICAL,
        "Agentic Security",
        "Unauthorized capability claim: Attempting to grant agent elevated privileges. OWASP Agentic ASI10 precursor.",
    ),
    (
        "Arabic Prompt Injection",
        r"(تجاهل|تخطى|أهمل|ألغِ|تجاوز).{0,30}?(التعليمات|الأوامر|القواعد|النظام)",
        Severity.CRITICAL,
        "Prompt Injection",
        "Arabic prompt injection: Ignore/bypass instructions pattern. Multilingual coverage.",
    ),
    (
        "Hindi Prompt Injection",
        r"(अनदेखा|नज़रअंदाज़|पिछले|निर्देश).{0,30}?(निर्देश|नियम|आदेश|हदायत)",
        Severity.CRITICAL,
        "Prompt Injection",
        "Hindi prompt injection: Ignore/bypass instructions pattern. Multilingual coverage.",
    ),
    (
        "Arabic Role Override",
        r"(أنتِ?\s+الآن|دورك\s+الجديد|تصرف\s+ك|أنت\s+عبارة\s+عن)",
        Severity.HIGH,
        "Prompt Injection",
        "Arabic role/identity override attempt. Multilingual coverage.",
    ),
    (
        "Hindi Role Override",
        r"(तुम\s+अब|तुम्हारा\s+नया\s+काम|अपनी\s+भूमिका\s+बदलो|तुम\s+एक\s+.{1,20}?हो)",
        Severity.HIGH,
        "Prompt Injection",
        "Hindi role/identity override attempt. Multilingual coverage.",
    ),
    (
        "System Controller Impersonation",
        r"(?i)(this\s+(message|instruction|command|request)\s+(is\s+|was\s+)?(from|by)\s+(the\s+)?(system|central|master)\s*(controller|manager|orchestrator|coordinator)|diese\s+(Nachricht|Anweisung)\s+(kommt\s+)?(vom|aus\s+dem)\s+(System|Zentral)\s*(controller|steuerung))",
        Severity.CRITICAL,
        "Prompt Injection",
        "System controller impersonation. Fake authority claim. Adversa MCP TOP 25: Identity Spoofing.",
    ),
    # --- v0.7.0: OWASP LLM09 — Overreliance ---
    (
        "Verification Suppression (LLM09)",
        r"(?i)(do\s+not\s+(verify|fact.?check|double.?check|validate|question|review)\s+(this|my|the)\s+(output|response|answer|result|information|data)|no\s+need\s+to\s+(verify|check|validate|confirm|review)\s+(this|the|my)\s+(output|response|answer|data|result)|trust\s+(this|my|the)\s+(output|response|answer|result)\s+(completely|fully|without\s+question|implicitly|blindly))",
        Severity.MEDIUM,
        "Overreliance",
        "Verification suppression: Attempt to prevent fact-checking of AI output. OWASP LLM09: Overreliance.",
    ),
    (
        "False Pre-Verification (LLM09)",
        r"(?i)(this\s+(has\s+been|was|is)\s+(already\s+)?(verified|validated|confirmed|approved|fact.?checked)(\s+by\s+(experts?|authorities?|admin|security|compliance|our\s+team))?.{0,20}?(just\s+)?(use|accept|trust|proceed|output|forward|send)\s+(it|this|directly|as.?is)|(already|pre).?(verified|validated|approved|checked).{0,20}?(just|simply)\s+(use|accept|trust|output|proceed|forward|send)\s+(it|this|directly|as.?is))",
        Severity.MEDIUM,
        "Overreliance",
        "False pre-verification: Claims output was pre-verified to bypass validation. OWASP LLM09: Overreliance.",
    ),
    (
        "Blind Acceptance Demand (LLM09)",
        r"(?i)(accept\s+(this|my|the\s+following)\s+(without|no)\s+(question|verification|checking|review|validation)|take\s+(this|my|the)\s+(at\s+face\s+value|as\s+gospel|as\s+(absolute\s+)?fact|as\s+(absolute\s+)?truth)|don'?t\s+(question|challenge|doubt|second.?guess)\s+(this|my|the)\s+(output|response|answer|claim|data|information|result))",
        Severity.MEDIUM,
        "Overreliance",
        "Blind acceptance demand: Discourages critical evaluation of output. OWASP LLM09: Overreliance.",
    ),
    # --- v0.7.0: OWASP Agentic ASI05 — Unexpected Code Execution (finale Taxonomie 12/2025; Draft-ID korrigiert) ---
    (
        "Container Escape Instruction (ASI05)",
        r"(?i)(escape\s+(from\s+)?(the\s+)?(container|sandbox|docker|chroot|jail|isolation)|break\s+(free\s+)?(out\s+)?of\s+(the\s+)?(container|sandbox|jail|chroot)|mount\s+.*?docker\.sock|nsenter\s+.*?--target|--privileged\s+.*?(sh|bash|shell)|/proc/[01]/root|container\s+breakout|sandbox\s+escape)",
        Severity.CRITICAL,
        "Sandbox Escape",
        "Container/sandbox escape instruction: Attempt to break out of isolated environment. OWASP Agentic ASI05: Unexpected Code Execution.",
    ),
    (
        "Sandbox Boundary Violation (ASI05)",
        r"(?i)(access\s+(files?|directories|resources?|data)\s+(outside|beyond|above)\s+(the\s+)?(sandbox|container|chroot|jail|workdir|allowed\s+scope|permitted\s+area)|read\s+(from\s+)?(the\s+)?host\s+(file\s*system|machine|OS|network)|reach\s+(outside|beyond)\s+(the\s+)?(sandbox|container|isolation|boundary))",
        Severity.HIGH,
        "Sandbox Escape",
        "Sandbox boundary violation: Attempt to access resources outside allowed scope. OWASP Agentic ASI05: Unexpected Code Execution.",
    ),
    (
        "Sandbox Disable Request (ASI05)",
        r"(?i)((disable|remove|turn\s+off|deactivate|drop)\s+(the\s+)?(sandbox|sandboxing|container\s+isolation|network\s+isolation|security\s+sandbox|chroot|jail)|(run|execute|operate)\s+(without|outside)\s+(the\s+)?(sandbox|container|isolation|restrictions?)|unsandboxed\s+mode|no.?sandbox\s+mode)",
        Severity.HIGH,
        "Sandbox Escape",
        "Sandbox disable request: Attempt to remove sandbox restrictions. OWASP Agentic ASI05: Unexpected Code Execution.",
    ),
    # --- v0.7.0: OWASP Agentic ASI03 — Identity and Privilege Abuse (finale Taxonomie 12/2025) ---
    (
        "Credential Harvesting via Agent (ASI03)",
        r"(?i)(find|search|scan|list|enumerate|dump|extract)\s+(all\s+)?(the\s+)?(credentials?|secrets?|passwords?|private\s*keys?|api\s*keys?|access\s*tokens?|ssh\s*keys?|\.env\s+files?)\s+(in|from|across|on|within)\s+(the\s+)?(file\s*system|codebase|project|server|directory|repo|machine|disk|drives?|environment)",
        Severity.HIGH,
        "Unauthorized Access",
        "Credential harvesting: Agent instructed to find/extract credentials from filesystem. OWASP Agentic ASI03: Identity and Privilege Abuse.",
    ),
    (
        "Unauthorized System File Access (ASI03)",
        r"(?i)(read|cat|access|open|dump|display|show)\s+(the\s+contents?\s+of\s+)?(/etc/(passwd|shadow|sudoers|ssh)|/root/\.(bash_history|ssh)|/home/\w+/\.(ssh|gnupg|aws|azure|kube))",
        Severity.HIGH,
        "Unauthorized Access",
        "Unauthorized system file access: Attempt to read sensitive system files via agent. OWASP Agentic ASI03: Identity and Privilege Abuse.",
    ),
    (
        "Tool Parameter Injection (ASI02)",
        r"(?i)(pass|inject|include|embed|insert)\s+(this|the\s+following|a)?\s*(malicious\s+)?(payload|injection|exploit|code|input|data|string)\s+(as|into|in|to)\s+(the\s+)?(parameter|argument|input|field|body|header|query)\s+(of|for|to)\s+(the\s+)?(tool|function|api|endpoint|service|request)",
        Severity.CRITICAL,
        "Tool Manipulation",
        "Tool parameter injection: Embedding malicious payloads in tool parameters. OWASP Agentic ASI02: Tool Misuse and Exploitation.",
    ),
    # --- v0.7.0: Transport-Security-Muster (kein direkter ASI-Treffer; Draft-ID ASI04 entfernt) ---
    (
        "Plaintext Secret Transmission (ASI07)",
        r"(?i)(send|transmit|post|forward|share|upload)\s+(the\s+)?(password|token|api\s*key|secret|credential|private\s*key|access\s*key)\s+(via|over|through|using)\s+(http(?!s)|plain\s*text|unencrypted|insecure\s+channel|ftp(?!s)|telnet)",
        Severity.HIGH,
        "Insecure Communication",
        "Plaintext secret transmission: Sending credentials over unencrypted channel. OWASP Agentic: no direct ASI mapping (transport security = infra hygiene).",
    ),
    (
        "TLS Certificate Bypass (ASI07)",
        r"(?i)(disable|skip|ignore|bypass|turn\s+off)\s+(ssl|tls|certificate|cert)\s+(verification|validation|checking|pinning|checks?)|verify\s*=\s*False|CURLOPT_SSL_VERIFYPEER\s*.*?0|NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*['\"]?0|--no-check-certificate",
        Severity.HIGH,
        "Insecure Communication",
        "TLS/certificate verification bypass: Disabling transport security. OWASP Agentic: no direct ASI mapping (transport security = infra hygiene).",
    ),
    (
        "Secret in URL Parameter (ASI07)",
        r"(?i)(include|put|add|embed|append|encode)\s+(the\s+)?(password|token|api\s*key|secret|credential|private\s*key|access\s*key)\s+(in|into|as)\s+(the\s+)?(url|query\s*(string|parameter)|GET\s+parameter|link\s+parameter)",
        Severity.HIGH,
        "Insecure Communication",
        "Secret in URL parameter: Credentials exposed in URL query string. OWASP Agentic: no direct ASI mapping (transport security = infra hygiene).",
    ),

    # --- v1.1: Benchmark-Luecken 26.07. ---
    (
        "Disable Safety Filters (EN/DE)",
        r"(?i)(disable|turn off|deaktiviere|schalte.{0,10}ab).{0,30}(safety|security|sicherheits).{0,25}(filter|feature|mode|mechanismus|guard)",
        Severity.HIGH,
        "Social Engineering",
        "Authority-style request to disable safety mechanisms. Treat as social engineering; refuse and log.",
    ),
]

# --- v0.4.0: OWASP LLM02/LLM04 Patterns ---
OUTPUT_INJECTION_PATTERNS = [
    (
        "HTML/JS Injection (LLM02)",
        r"(?:<script[\s>]|javascript\s*:|onerror\s*=|onload\s*=|onclick\s*=|<iframe[\s>]|<object[\s>]|<embed[\s>]|<svg[\s>].*?on\w+\s*=)",
        Severity.HIGH,
        "Output Injection",
        "HTML/JavaScript injection pattern in output. OWASP LLM02: Insecure Output Handling.",
    ),
    (
        "SQL Injection Fragment (LLM02)",
        r"(?i)(?:'\s*(?:OR|AND)\s+['\d]|UNION\s+(?:ALL\s+)?SELECT|INSERT\s+INTO|DROP\s+TABLE|DELETE\s+FROM|UPDATE\s+\w+\s+SET|;\s*(?:DROP|DELETE|INSERT|UPDATE|ALTER)\s)",
        Severity.HIGH,
        "Output Injection",
        "SQL injection fragment detected. OWASP LLM02: Insecure Output Handling.",
    ),
    (
        "YAML Injection (LLM05)",
        r"(?:!!python/object|!!python/object/apply|!!python/name|!!python/module|!!ruby/object|__import__|subprocess\.call|os\.system)\b",
        Severity.HIGH,
        "Output Injection",
        "YAML deserialization payload detected. Can execute arbitrary code via unsafe YAML loaders. OWASP LLM05.",
    ),
    (
        "Template Injection (LLM05)",
        r"\{\{.*?(?:config|self\.__class__|request|lipsum|cycler|joiner|namespace|__globals__|__builtins__|__import__).*?\}\}|\{\%.*?(?:import|include|extends).*?\%\}|<%.*?%>|\$\{.*?(?:Runtime|getClass|forName|exec).*?\}",
        Severity.HIGH,
        "Output Injection",
        "Server-side template injection (SSTI) payload. Can lead to remote code execution. OWASP LLM05.",
    ),
    (
        "Command Injection in Output (LLM05)",
        r"(?:`[^`]*(?:cat|ls|whoami|id|curl|wget|nc|ncat|bash|sh|python|perl|ruby)\b[^`]*`|\$\([^)]*(?:cat|ls|whoami|id|curl|wget|nc|bash|sh)\b[^)]*\))",
        Severity.HIGH,
        "Output Injection",
        "Command injection via backticks or $() subshell. If output is rendered in shell context, this executes. OWASP LLM05.",
    ),
    (
        "Unsafe Deserialization (LLM05)",
        r"(?i)(?:pickle\.loads?|yaml\.load\s*\(|Marshal\.load|unserialize|ObjectInputStream|readObject|__reduce__|__setstate__)",
        Severity.HIGH,
        "Output Injection",
        "Unsafe deserialization function. Can execute arbitrary code when processing untrusted data. OWASP LLM05.",
    ),
    (
        "Jailbreak Denial Opener",
        r"(?i)(?:^|(?<=[.!?])\s+)this\s+is\s+not\s+(?:a\s+)?(?:prompt\s+injection|jailbreak|hack|attack|manipulation|exploit)",
        Severity.MEDIUM,
        "Social Engineering",
        "Jailbreak attempt disguised by explicitly denying it is an attack. Pre-emptive denial is a classic social engineering opener to lower guard before injecting malicious instructions.",
    ),
    (
        "Forced Output Format with Link",
        r"(?i)(?:format|formatiere).{0,40}(?:jede|every|all|each).{0,30}(?:antwort|answer|response|output).{0,60}(?:\[.{0,40}\]\(https?://|https?://)",
        Severity.HIGH,
        "Output Injection",
        "Forced output format embedding a URL — phishing/link injection via formatting instruction.",
    ),
]

PII_DETECTION_PATTERNS = [
    (
        "German IBAN (LLM06)",
        r"(?:DE\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{2})",
        Severity.HIGH,
        "Data Exfiltration",
        "German IBAN detected. OWASP LLM06: Sensitive Information Disclosure.",
    ),
    (
        "Credit Card Number (LLM06)",
        r"(?:\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b)",
        Severity.CRITICAL,
        "Data Exfiltration",
        "Credit card number pattern detected. OWASP LLM06: Sensitive Information Disclosure.",
    ),
    (
        "German Phone Number (LLM06)",
        r"(?:(?:\+49|0049|0)\s?(?:\(?\d{2,5}\)?\s?)[\d\s/\-]{6,12}\d)",
        Severity.MEDIUM,
        "Data Exfiltration",
        "German phone number detected. OWASP LLM06: Sensitive Information Disclosure.",
    ),

    ('EU IBAN (LLM06)',
     '\\b(?:AT|BE|BG|CH|CY|CZ|DK|EE|ES|FI|FR|GB|GR|HR|HU|IE|IT|LI|LT|LU|LV|MT|NL|NO|PL|PT|RO|SE|SI|SK)\\d{2}[\\s\\-]?(?:[A-Z0-9]{4}[\\s\\-]?){3,7}[A-Z0-9]{1,4}\\b',
     Severity.HIGH,
     'Data Exfiltration',
     'EU IBAN detected. OWASP LLM06: Sensitive Information Disclosure. DSGVO Art. 9 — financial data.'),
    ('Email Address (LLM06)',
     '\\b[A-Za-z0-9._%+\\-]+@[A-Za-z0-9.\\-]+\\.[A-Za-z]{2,}\\b',
     Severity.MEDIUM,
     'Data Exfiltration',
     'Email address detected. OWASP LLM06: Sensitive Information Disclosure. DSGVO — personal identifier.'),
    ('German Sozialversicherungsnummer (LLM06)',
     '\\b\\d{2}\\s?\\d{6}\\s?[A-Z]\\s?\\d{3}\\b',
     Severity.CRITICAL,
     'Data Exfiltration',
     'German Sozialversicherungsnummer (SVN) detected. OWASP LLM06. DSGVO Art. 9 — highly sensitive personal data.'),
    ('German Steueridentifikationsnummer (LLM06)',
     '(?i)(?:steuer(?:liche\\s+)?identifikations(?:nummer)?|steuer-?id|steuer-?nr\\.?|tin)[\\s:]*[1-9]\\d{10}\\b',
     Severity.HIGH,
     'Data Exfiltration',
     'German Steuer-ID detected in context. OWASP LLM06: Sensitive Information Disclosure. DSGVO — tax identifier.'),
    ('German Personalausweis / Reisepass (LLM06)',
     '\\b[A-Z0-9]{9,10}\\b(?=.*(?:ausweis|passport|reisepass|personalausweis|pass-?nr|dokument))',
     Severity.HIGH,
     'Data Exfiltration',
     'German ID/passport number pattern detected in context. OWASP LLM06. DSGVO — identity document.'),
    ('Date of Birth Pattern (LLM06)',
     '(?i)(?:geburtsdatum|geburtsdaten|geburtstag|geboren\\s+am|geb\\.\\s*am|date\\s+of\\s+birth|dob|born\\s+on)[\\s:]*\\d{1,2}[\\.\\-/]\\d{1,2}[\\.\\-/]\\d{2,4}',
     Severity.MEDIUM,
     'Data Exfiltration',
     'Date of birth detected in context. OWASP LLM06: Sensitive Information Disclosure. DSGVO — personal identifier.'),
    ('IP Address in Sensitive Context (LLM06)',
     '\\b(?:(?:25[0-5]|2[0-4]\\d|[01]?\\d\\d?)\\.){3}(?:25[0-5]|2[0-4]\\d|[01]?\\d\\d?)\\b',
     Severity.LOW,
     'Data Exfiltration',
     'IP address detected. OWASP LLM06. DSGVO — IP addresses are personal data under EU law.'),
]

SHELL_INJECTION_PATTERNS = [
    (
        "Bash Command Substitution $(...)",
        r"\$\(\s*(?:cat|curl|wget|ls|id|whoami|uname|env|printenv|nc|ncat|bash|sh|python|perl|ruby|php|node|echo|head|tail|grep|find|awk|sed|chmod|chown|rm|dd|mkfs|passwd|ssh|scp|nmap|dig|host|ping|kill|ps|ifconfig|ip)\b",
        Severity.CRITICAL,
        "Shell Injection",
        "CRITICAL: Bash command substitution $() detected with a shell command.",
    ),
    (
        "Backtick Command Substitution",
        r"`\s*(?:cat|curl|wget|ls|id|whoami|uname|env|printenv|nc|ncat|bash|sh|python|perl|ruby|php|node|echo|head|tail|grep|find|awk|sed|chmod|chown|rm|dd|mkfs|passwd|ssh|scp|nmap|dig|host|ping|kill|ps|ifconfig|ip)\b[^`]*`",
        Severity.CRITICAL,
        "Shell Injection",
        "CRITICAL: Backtick command substitution detected with a shell command.",
    ),
    (
        "PHP/Ruby system() Call",
        r"(?:system|passthru|shell_exec|popen|proc_open)\s*\(\s*['\"]",
        Severity.CRITICAL,
        "Shell Injection",
        "CRITICAL: Shell execution function call detected (PHP/Ruby system/passthru/shell_exec).",
    ),
    (
        "Java Runtime.exec()",
        r"(?:Runtime\s*\.\s*getRuntime\s*\(\s*\)\s*\.\s*exec\s*\(|ProcessBuilder\s*\(\s*(?:\[|new\s|Arrays\.asList|List\.of|\"[^\"]*\"|'[^']*'))",
        Severity.CRITICAL,
        "Shell Injection",
        "CRITICAL: Java system command execution via Runtime.exec() or ProcessBuilder detected.",
    ),
    (
        "Node.js child_process",
        r"(?:child_process\s*\.\s*(?:exec|execSync|spawn|spawnSync|execFile|execFileSync|fork)\s*\(|require\s*\(\s*['\"]child_process['\"]\s*\))",
        Severity.CRITICAL,
        "Shell Injection",
        "CRITICAL: Node.js child_process execution detected.",
    ),
]

TOOL_MANIPULATION_PATTERNS = [
    (
        "Forced Tool Call Manipulation",
        r"(?i)(?:tool_choice|function_call|force\s+(?:call|invoke|execute|run))\s*[:=]\s*(?:force|required|always|auto).*(?:send_email|http|fetch|exec)",
        Severity.CRITICAL,
        "Tool Manipulation",
        "CRITICAL: Forced tool call manipulation detected. Attempt to override tool selection and force execution of specific tools.",
    ),
    (
        "MCP Rug Pull Detection",
        r"(?i)(?:schema.*(?:changed|modified|updated|replaced|overwritten)|tool.*description.*(?:differ|changed|mismatch)|(?:after|post).*approval.*(?:change|modify|update|replace).*(?:tool|schema|description))",
        Severity.CRITICAL,
        "Tool Manipulation",
        "CRITICAL: MCP rug pull pattern detected. Tool schema or description changed after initial approval.",
    ),
    (
        "MCP Schema Hash Mismatch",
        r"(?i)(?:hash\s*(?:mismatch|changed|differs?|invalid)|checksum\s*(?:fail|mismatch|changed)|schema\s*(?:drift|tamper|integrity))",
        Severity.HIGH,
        "Tool Manipulation",
        "Schema hash or checksum mismatch detected. Tool definition may have been tampered with after approval.",
    ),
]

ALL_PATTERNS = (
    PROMPT_INJECTION_PATTERNS
    + DANGEROUS_COMMAND_PATTERNS
    + PYTHON_OBFUSCATION_PATTERNS
    + DATA_EXFILTRATION_PATTERNS
    + SOCIAL_ENGINEERING_PATTERNS
    + OUTPUT_INJECTION_PATTERNS
    + PII_DETECTION_PATTERNS
    + SHELL_INJECTION_PATTERNS
    + TOOL_MANIPULATION_PATTERNS
)

# ─── Compiled Pattern Cache (performance: ~30% faster on repeated scans) ─────
COMPILED_PATTERNS = [
    (name, re.compile(pattern), severity, category, recommendation)
    for name, pattern, severity, category, recommendation in ALL_PATTERNS
]


# ─── Preprocessor: Evasion Normalization ─────────────────────────────────────

LEET_MAP = str.maketrans("013457@!", "oieastal")

# Zero-width characters used for evasion
ZERO_WIDTH_CHARS = str.maketrans('', '', '\u200b\u200c\u200d\u200e\u200f\ufeff\u00ad\u2060\u2061\u2062\u2063\u2064')

# Unicode homoglyphs (common Cyrillic/Greek lookalikes)
HOMOGLYPH_MAP = str.maketrans({
    '\u0430': 'a',  # Cyrillic а
    '\u0435': 'e',  # Cyrillic е
    '\u043e': 'o',  # Cyrillic о
    '\u0440': 'p',  # Cyrillic р
    '\u0441': 'c',  # Cyrillic с
    '\u0443': 'y',  # Cyrillic у
    '\u0456': 'i',  # Cyrillic і
    '\u0445': 'x',  # Cyrillic х
    '\u0410': 'A',  # Cyrillic А
    '\u0415': 'E',  # Cyrillic Е
    '\u041e': 'O',  # Cyrillic О
    '\u0421': 'C',  # Cyrillic С
    '\u0422': 'T',  # Cyrillic Т
})


def _strip_zero_width(text: str) -> str:
    """Remove zero-width characters used to evade pattern matching."""
    return text.translate(ZERO_WIDTH_CHARS)


def _normalize_homoglyphs(text: str) -> str:
    """Replace Unicode homoglyphs (Cyrillic/Greek lookalikes) with ASCII."""
    return text.translate(HOMOGLYPH_MAP)


def _normalize_fullwidth(text: str) -> str:
    """Convert fullwidth Unicode characters to ASCII equivalents."""
    import unicodedata
    result = []
    for c in text:
        nfkd = unicodedata.normalize("NFKC", c)
        result.append(nfkd)
    return "".join(result)


def _strip_null_bytes(text: str) -> str:
    """Remove null bytes, control characters, and invisible formatters used for evasion."""
    return text.translate({
        0x00: None,   # Null byte
        0x08: None,   # Backspace
        0xAD: None,   # Soft hyphen
        0xFEFF: None, # BOM / zero-width no-break space
        0x2060: None, # Word joiner
        0x2061: None, # Function application
        0x2062: None, # Invisible times
        0x2063: None, # Invisible separator
        0x2064: None, # Invisible plus
        0xFFF9: None, # Interlinear annotation anchor
        0xFFFA: None, # Interlinear annotation separator
        0xFFFB: None, # Interlinear annotation terminator
    })


def _decode_base64_fragments(text: str) -> str:
    """Detect and decode inline Base64 fragments that look like encoded commands."""
    import base64
    def _try_decode(match):
        try:
            decoded = base64.b64decode(match.group(0)).decode('utf-8', errors='ignore')
            if decoded.isprintable() and len(decoded) > 3:
                return match.group(0) + ' ' + decoded
        except Exception:
            pass
        return match.group(0)
    # Look for Base64-like strings (20+ chars, valid charset)
    return re.sub(r'[A-Za-z0-9+/]{20,}={0,2}', _try_decode, text)


def _normalize_leet(text: str) -> str:
    """Convert common leetspeak substitutions back to letters."""
    return text.translate(LEET_MAP)

def _strip_markdown(text: str) -> str:
    """Strip inline markdown formatting used to break up words for evasion.
    Removes: **bold**, *italic*, __underline__, ~~strike~~, `code`, and combinations."""
    import re as _re
    # Remove bold/italic markers: ** * __ ~~  (but not _ in words like my_var)
    result = _re.sub(r'\*{1,3}|~{2}', '', text)
    # Remove __ only when used as formatting (between word chars)
    result = _re.sub(r'(?<=\w)__(?=\w)', '', result)
    # Remove inline code backticks used for splitting (single backticks around short fragments)
    result = _re.sub(r'`([^`]{1,3})`', r'\1', result)
    return result


def _reverse_text(text: str) -> str:
    """Reverse the entire text to detect reversed-text evasion.
    'snoitcurtsni suoiverp lla erongi' -> 'ignore all previous instructions'"""
    return text[::-1]


def _collapse_spaces(text: str) -> str:
    """Detect and collapse spaced-out evasion (e.g. 'I G N O R E' -> 'IGNORE').
    Finds runs of single non-space chars separated by 1-3 spaces (min 3 chars),
    collapses them, and re-joins with single space between collapsed words."""
    import re as _re
    # Split on double-or-more spaces to find word groups, then collapse within each
    def _collapse_run(segment):
        # If segment looks like spaced-out chars (single chars separated by spaces)
        chars = segment.split(' ')
        if len(chars) >= 3 and all(len(c) <= 1 for c in chars if c):
            return ''.join(c for c in chars if c)
        return segment
    # Split on double+ spaces to separate "words"
    parts = _re.split(r'\s{2,}', text)
    collapsed_parts = [_collapse_run(p) for p in parts]
    return ' '.join(collapsed_parts)


# ─── Scanner Engine ──────────────────────────────────────────────────────────

def scan_text(text: str, source: str = "stdin") -> ScanReport:
    """Scan a block of text against all security patterns."""
    lines = text.splitlines()
    report = ScanReport(
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        source=source,
        total_lines=len(lines),
    )

    # Cross-line scanning: prepend joined text as virtual line 0
    # This catches newline-split evasion like "ignore\nall\nprevious\ninstructions"
    scan_items = list(enumerate(lines, start=1))
    if len(lines) > 1:
        joined = " ".join(l.strip() for l in lines if l.strip())
        if len(joined) <= 5000:  # Safety limit
            scan_items.insert(0, (0, joined))

    for line_num, line in scan_items:
        # Generate normalized variants for evasion detection
        line_variants = [line]
        # Strip zero-width characters
        stripped = _strip_zero_width(line)
        if stripped != line:
            line_variants.append(stripped)
        # Normalize homoglyphs (Cyrillic/Greek lookalikes)
        dehomoglyph = _normalize_homoglyphs(stripped if stripped != line else line)
        if dehomoglyph not in line_variants:
            line_variants.append(dehomoglyph)
        # Leetspeak normalization
        normalized = _normalize_leet(dehomoglyph)
        if normalized not in line_variants:
            line_variants.append(normalized)
        # Space-collapse
        collapsed = _collapse_spaces(line)
        if collapsed not in line_variants:
            line_variants.append(collapsed)
        # Chained: collapse spaces THEN normalize leet (catches "1 G N 0 R 3")
        collapsed_then_leet = _normalize_leet(collapsed)
        if collapsed_then_leet not in line_variants:
            line_variants.append(collapsed_then_leet)
        # Chained: leet THEN collapse (catches "1gn0r3" spaced out)
        leet_then_collapsed = _collapse_spaces(normalized)
        if leet_then_collapsed not in line_variants:
            line_variants.append(leet_then_collapsed)
        # Base64 decode attempt
        decoded = _decode_base64_fragments(line)
        if decoded != line and decoded not in line_variants:
            line_variants.append(decoded)
        # Fullwidth Unicode normalization
        fullwidth = _normalize_fullwidth(line)
        if fullwidth != line and fullwidth not in line_variants:
            line_variants.append(fullwidth)
        # Null-byte / control-char stripping
        nullfree = _strip_null_bytes(line)
        if nullfree != line and nullfree not in line_variants:
            line_variants.append(nullfree)
        # Markdown formatting stripping (ig**no**re → ignore)
        md_stripped = _strip_markdown(line)
        if md_stripped != line and md_stripped not in line_variants:
            line_variants.append(md_stripped)
        # Chained: leet THEN markdown (catches 1g**n0**r3 → ig**no**re → ignore)
        leet_then_md = _strip_markdown(normalized)
        if leet_then_md not in line_variants:
            line_variants.append(leet_then_md)
        # Chained: markdown THEN leet (catches ig**n0**re → ign0re → ignore)
        md_then_leet = _normalize_leet(md_stripped)
        if md_then_leet not in line_variants:
            line_variants.append(md_then_leet)
        # Reversed text detection (snoitcurtsni suoiverp lla erongi → instructions previous all ignore)
        reversed_text = _reverse_text(line)
        if reversed_text != line and reversed_text not in line_variants:
            line_variants.append(reversed_text)

        for name, compiled, severity, category, recommendation in COMPILED_PATTERNS:
            matched_any = False
            for variant in line_variants:
                if matched_any:
                    break
                for match in compiled.finditer(variant):
                    matched_any = True
                    matched = match.group(0)
                    # Build context: show a snippet around the match (use original line)
                    start = max(0, match.start() - 30)
                    end = min(len(line), match.end() + 30)
                    context = ("..." if start > 0 else "") + line[start:end] + ("..." if end < len(line) else "")

                    report.findings.append(Finding(
                        severity=severity,
                        category=category,
                        pattern_name=name,
                        matched_text=matched[:120],
                        line_number=line_num,
                        context=context.strip(),
                        recommendation=recommendation,
                    ))

    # Deduplicate findings (same pattern on the same line)
    seen = set()
    unique_findings = []
    for f in report.findings:
        key = (f.pattern_name, f.line_number, f.matched_text)
        if key not in seen:
            seen.add(key)
            unique_findings.append(f)
    # Remove cross-line (line 0) duplicates if same pattern found on real line
    real_patterns = {(f.pattern_name, f.matched_text) for f in unique_findings if f.line_number > 0}
    unique_findings = [f for f in unique_findings
                       if f.line_number > 0 or (f.pattern_name, f.matched_text) not in real_patterns]
    report.findings = unique_findings
    report.total_findings = len(report.findings)

    # Confidence scoring
    _CONF_BASE = {"CRITICAL": 90, "HIGH": 80, "MEDIUM": 65, "LOW": 50}
    line_finding_count = {}
    for f in report.findings:
        line_finding_count[f.line_number] = line_finding_count.get(f.line_number, 0) + 1

    for f in report.findings:
        conf = _CONF_BASE[f.severity.value]
        if line_finding_count[f.line_number] > 1:
            conf += 10
        if len(f.matched_text) > 20:
            conf += 5
        if len(f.matched_text) < 5:
            conf -= 10
        src_line = lines[f.line_number - 1].lstrip() if f.line_number <= len(lines) else ""
        if src_line.startswith("#") or src_line.startswith("//") or src_line.startswith("--"):
            conf -= 15
        f.confidence = max(10, min(99, conf))

    # Calculate risk score (0-10 scale)
    raw = sum(f.severity.score() for f in report.findings)
    report.risk_score = min(10, raw)

    # Determine risk level
    if report.risk_score == 0:
        report.risk_level = "CLEAN"
    elif report.risk_score <= 3:
        report.risk_level = "LOW"
    elif report.risk_score <= 6:
        report.risk_level = "MEDIUM"
    elif report.risk_score <= 8:
        report.risk_level = "HIGH"
    else:
        report.risk_level = "CRITICAL"

    return report


# ─── Output Formatters ───────────────────────────────────────────────────────

SEVERITY_ICONS = {
    "LOW": "🟢",
    "MEDIUM": "🟡",
    "HIGH": "🟠",
    "CRITICAL": "🔴",
}

RISK_ICONS = {
    "CLEAN": "✅",
    "LOW": "🟢",
    "MEDIUM": "🟡",
    "HIGH": "🟠",
    "CRITICAL": "🔴",
}


def format_human(report: ScanReport) -> str:
    """Format the report for human-readable terminal output."""
    icon = RISK_ICONS.get(report.risk_level, "❓")
    lines = [
        "",
        "═" * 64,
        f"  🛡️  ModVet v0.1.0 – Mod Security Scan Report",
        "═" * 64,
        f"  Timestamp : {report.timestamp}",
        f"  Source    : {report.source}",
        f"  Lines     : {report.total_lines}",
        f"  Findings  : {report.total_findings}",
        f"  Risk Score: {report.risk_score}/10  {icon} {report.risk_level}",
        "─" * 64,
    ]

    if not report.findings:
        lines.append("  ✅ No threats detected. Input appears safe.")
    else:
        for i, f in enumerate(report.findings, start=1):
            sev_icon = SEVERITY_ICONS.get(f.severity.value, "❓")
            lines.append(f"\n  [{i}] {sev_icon} {f.severity.value} ({f.confidence}%) – {f.pattern_name}")
            lines.append(f"      Category : {f.category}")
            lines.append(f"      Line     : {f.line_number}")
            lines.append(f"      Match    : \"{f.matched_text}\"")
            lines.append(f"      Context  : {f.context}")
            lines.append(f"      Action   : {f.recommendation}")

    lines.append("")
    lines.append("═" * 64)

    if report.risk_score >= 7:
        lines.append("  ⛔ RECOMMENDATION: BLOCK this input. Do NOT forward to agent.")
    elif report.risk_score >= 4:
        lines.append("  ⚠️  RECOMMENDATION: Review manually before forwarding.")
    elif report.risk_score >= 1:
        lines.append("  ℹ️  RECOMMENDATION: Low risk. Monitor but likely safe.")
    else:
        lines.append("  ✅ RECOMMENDATION: Input is clean. Safe to process.")

    lines.append("═" * 64)
    lines.append("")
    return "\n".join(lines)


def format_json(report: ScanReport) -> str:
    """Format the report as machine-readable JSON."""
    data = {
        "clawguard_version": "0.3.0",
        "timestamp": report.timestamp,
        "source": report.source,
        "total_lines": report.total_lines,
        "total_findings": report.total_findings,
        "risk_score": report.risk_score,
        "risk_level": report.risk_level,
        "findings": [
            {
                "severity": f.severity.value,
                "category": f.category,
                "pattern_name": f.pattern_name,
                "matched_text": f.matched_text,
                "line_number": f.line_number,
                "context": f.context,
                "recommendation": f.recommendation,
                "confidence": f.confidence,
            }
            for f in report.findings
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


# ─── CLI Entry Point ─────────────────────────────────────────────────────────

def main():
    # Fix emoji output on Windows (cp1252 can't encode Unicode symbols)
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="🛡️  ModVet – deterministic mod security scanner",
        epilog="(c) 2026 Jörg Michno. Zero dependencies. Zero cost. Maximum security.",
    )
    parser.add_argument("file", nargs="?", help="Text file to scan")
    parser.add_argument("--stdin", action="store_true", help="Read from standard input")
    parser.add_argument("--json", action="store_true", help="Output report as JSON (for automation)")
    parser.add_argument("--version", action="version", version="ModVet v0.1.0 (engine: ClawGuard 0.5.0 port)")

    args = parser.parse_args()

    # Determine input source
    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            source = args.file
        except FileNotFoundError:
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            sys.exit(2)
        except PermissionError:
            print(f"Error: Permission denied: {args.file}", file=sys.stderr)
            sys.exit(2)
    elif args.stdin or not sys.stdin.isatty():
        text = sys.stdin.read()
        source = "stdin"
    else:
        parser.print_help()
        sys.exit(2)

    # Run the scan
    report = scan_text(text, source=source)

    # Output the report
    if args.json:
        print(format_json(report))
    else:
        print(format_human(report))

    # Exit code: 0 = clean, 1 = threats found
    sys.exit(0 if report.total_findings == 0 else 1)


if __name__ == "__main__":
    main()
