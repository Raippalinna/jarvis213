"""Avgränsade specialistagenter: genererar utkast, verkställer aldrig åtgärder."""
from dataclasses import dataclass
from langchain_core.messages import AIMessage, HumanMessage


@dataclass(frozen=True)
class SpecialistAgent:
    name: str
    instruction: str
    capabilities: tuple[str, ...]
    execution_mode: str = "draft_only"

    def messages(self, system: str, history: list) -> list[dict[str, str]]:
        if not history or not isinstance(history[-1], HumanMessage):
            raise ValueError("En aktuell användaruppgift krävs")
        output = [{"role": "system", "content": (
            system + "\n" + self.instruction
            + "\nDu producerar endast utkast. Du har inga verktyg för att läsa webben, "
            "ändra kod, skicka meddelanden eller verkställa beslut. Påstå inte att det har skett."
        )}]
        budget = 16000
        selected = []
        for item in reversed(history[-12:]):
            if not isinstance(item, (HumanMessage, AIMessage)):
                continue
            text = str(item.content)
            if len(text) > budget:
                if not selected:
                    raise ValueError("Uppgiften överskrider agentens kontextgräns")
                break
            budget -= len(text)
            selected.append({"role": "user" if isinstance(item, HumanMessage) else "assistant",
                             "content": text})
        return output + list(reversed(selected))


AGENTS = {
    "researcher": SpecialistAgent("researcher", "Separera källbelagt underlag från hypoteser.", ("research_draft",)),
    "coder": SpecialistAgent("coder", "Leverera kodförslag och testfall, inte påstådda kodändringar.", ("code_draft",)),
    "analyst": SpecialistAgent("analyst", "Visa antaganden, enheter och beräkningar.", ("analysis_draft",)),
    "architect": SpecialistAgent("architect", "Beskriv systemgränser, ansvar och godkännandegrindar.", ("architecture_draft",)),
    "casual": SpecialistAgent("casual", "Svara kort och direkt.", ("conversation",)),
    "strategist": SpecialistAgent("strategist", "Prioritera efter verifierat underlag och ange nästa kontrollpunkt.", ("strategy_draft",)),
}


def get_agent(name: str) -> SpecialistAgent:
    return AGENTS[name]
