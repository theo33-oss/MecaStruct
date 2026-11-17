

def test_cisaillement_tous_les_modes_comptent_dans_le_verdict():
    """Un mode non admissible (Jourawski, clavette, goupille, matage, τ) rend le cisaillement « NON vérifié »."""
    import json

    from mecastruct.pont import noyau

    noyau.charger("machines"), noyau.charger("outils"), noyau.charger("structures")
    d = json.loads(json.dumps(noyau.tous_formulaires()["cis"]["defaut"]))

    def verdict(**modif):
        so = json.loads(noyau.appeler("cis", json.dumps({**d, **modif})))["sortie"]
        return so["ok"], so["status"], [c for c in so["criteres"] if not c["ok"]]

    ok, status, ko = verdict()
    assert ok is True and not ko
    assert all(x in status for x in ("Jourawski : vérifié", "Clavette : vérifié", "Goupille : vérifié"))
    for modif, nom in (({"T": 14.0}, "τ max"), ({"Padm": 40.0}, "matage"), ({"Lk": 30.0}, "clavette"),
                       ({"C": 3.0}, "clavette"), ({"Fp": 12.0}, "goupille"), ({"np": 1, "Fp": 5.0}, "goupille")):
        ok, status, ko = verdict(**modif)
        assert ok is False and "NON vérifié" in status and ko, (nom, status)
    assert "Clavette : NON vérifié" in verdict(Lk=30.0)[1]
    assert "Goupille : NON vérifié" in verdict(Fp=12.0)[1]
