# Komplettering till PR #23

Status: FÖRBERETT. Denna commit sparar en patch, inte applicerad körkod. Ingen merge eller driftsättning.

Granskad bas: 77bd8bc58378909245ab340665c4e3b49f8082ff.

Fynd: platshållaren (tomt svar från modellen) får kvalitet 0,8 för en direkt fråga trots att minneslagringen spärrar den. Patchen ändrar enbart kvalitetsvillkoret och lägger till sju regressionstestfall.

Testbevis: sju isolerade fall passerade på en kopia av poängfunktionens exekverbara kod. Strategi- och formatklassificering stubbades för direkta frågor utan formatkrav. Detta är inte fullständig repo-, integrations- eller driftstestning. Pytest-filen har inte körts mot importerad supervisor.

Återstår: kontrollera aktuell diff och bas, kör git apply --check på patchen, applicera den, kör python -m pytest tests -q, granska hemligheter och återläs sparad kod. Separat godkännande krävs för skrivning, merge och produktionssättning.

Återställning: denna förberedelse kan tas bort utan påverkan på körkod. Efter eventuell applicering återställs enradsvillkoret och den nya testfilen tas bort, alternativt revert av den framtida kodcommitten. Inga data-, schema-, budget- eller behörighetsändringar.
