"""D168 (M9): a character's body nobody has set is seeded from its sheet's words — the figure, the build, the height — before it is fitted;
a body the author set is never touched. The market walk's three: Bram, Hanne, Mira."""


def test_the_words_say_the_body():
    from loom2.body import body_from_words
    bram = body_from_words("a heavy-set man in his fifties, a bald head, a thick grey beard, ruddy cheeks, strong forearms a faded blue anchor tattoo on his right forearm")
    assert bram == {"figure": "male", "build": "heavy", "height_m": 1.78}
    hanne = body_from_words("a small elderly woman in her seventies, white hair in a low bun, a kind lined face round wire spectacles")
    assert hanne == {"figure": "female", "height_m": 1.53}
    mira = body_from_words("a woman in her early thirties, a long dark braid down her back, a strong straight nose and high cheekbones")
    assert mira == {"figure": "female", "height_m": 1.66}
    assert body_from_words("a tall slender man") == {"figure": "male", "build": "slim", "height_m": 1.9}
    assert body_from_words("a little girl with pigtails") == {"figure": "female", "height_m": 1.25}
    assert body_from_words("a robot made of brass") == {}                         # nothing said: the defaults stay
    assert body_from_words("a man and a woman") == {"height_m": 1.75} or body_from_words("a man and a woman") == {}   # a tie names no figure


def test_only_an_untouched_body_is_seeded():
    from loom2.body import Body, seed_body
    seeded = seed_body(None, "a heavy-set man")
    assert (seeded.figure, seeded.build, seeded.height_m) == ("male", "heavy", 1.78)
    assert seed_body(Body(), "a heavy-set man").figure == "male"                  # Body's defaults: never set
    mine = Body(height_m=1.62, figure="female")
    assert seed_body(mine, "a heavy-set man") is mine                              # the author's body stays theirs
