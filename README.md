# moneyglitch

## Disclaimer: 
IHR SEID FÜR ALLES IN EUREM DEPOT SELBER VERANTWORTLICH !!! 

## Wie es funktioniert: 

1. Tragt eure Login-Daten und Api-Access Daten in properties.yml ein
2. tragt in der main.py eure Daten zum Produkt ein (direkt unter der Zeile if __name__ == "__main__": ), welches ihr handeln wollt.
3. Entscheiden ob ihr Einzelausführung oder Endlosausführung wollt, entsprechend die letzten 2 Zeilen der main.py einkommentieren

## Bemerkung zur Tan: 
Das Programm unterstützt lediglich die push-tan Funktion über die ComD App


## Was das Programm macht: 
1. Verifizierung einer Tan-Session, bzw. automatischer Update einer noch aktiven Tan-Session
2. Wählt ein Depot aus, gibt es mehrere wählt er das erste, das von der Api geliefert wird (FALLS IHR MEHRER DEPOTS HABT, BITTE AUFPASSEN, evt. IF abfrage einbauen)
3. Programm versucht aktuellen Spread eures Produkts über die ComD Website zu ermitteln (nicht über die Api)
4. Falls Spread niedrig genug (könnt ihr über "accepted_spread" in main.py einstellen) erstellt das Programm eine Buy-Quote
5. Sobald der Buy-Quote  expirered wird eine neue erstellt, sobald executet wird entsprechende Sell-Quote erstellt
6. Nach execution wird in trades.json die Trade Details abgespeichert
7. Über Konsole wird Spread des letzten trades mitgeteilt


## trades_analize
Das Skript wertet die getätigten Trades aus und zeigt "Gewinn" (unter der Annahme, dass die ComD den CashBack überweist)

