from model import Direction, House, Room
from render import (
    _render_tile,
    adjacency_count,
    calc_cols,
    format_legend,
    has_door,
    layout_dims,
    legend_entries,
    near_entrance_dist,
    render_side_by_side,
    render_text,
    room_symbol,
)


def test_room_symbol_legend():
    room = Room("Kitchen", Direction(0), legend="K")
    assert room_symbol(room) == "K"


def test_room_symbol_first_letter():
    room = Room("Parlour", Direction(0))
    assert room_symbol(room) == "P"


def test_room_symbol_none():
    assert room_symbol(None) == "?"


def test_render_tile_empty_shown():
    h = House(3, 3)
    top, mid, bot = _render_tile(h, 1, 1, False, True)
    assert top == "\u00b7 \u00b7"
    assert mid == "   "
    assert bot == "\u00b7 \u00b7"


def test_render_tile_empty_hidden():
    h = House(3, 3)
    top, mid, bot = _render_tile(h, 1, 1, False, False)
    assert top == "   "
    assert mid == "   "
    assert bot == "   "


def test_render_tile_entrance_border():
    h = House(3, 3)
    h.place_room(1, 1, Room("G", Direction(0)))
    top, mid, bot = _render_tile(h, 1, 1, True, False)
    assert top.startswith("╔") and top.endswith("╗")
    assert mid.startswith("║") and mid.endswith("║")
    assert bot.startswith("╚") and bot.endswith("╝")


def test_render_tile_normal_border():
    h = House(3, 3)
    h.place_room(1, 1, Room("A", Direction(0)))
    top, mid, bot = _render_tile(h, 1, 1, False, False)
    assert top.startswith("┌") and top.endswith("┐")
    assert mid.startswith("│") and mid.endswith("│")
    assert bot.startswith("└") and bot.endswith("┘")


def test_has_door_room_has_direction():
    h = House(3, 3)
    r = Room("A", Direction.E)
    h.place_room(1, 1, r)
    assert has_door(h, r, 1, 1, Direction.E)
    assert not has_door(h, r, 1, 1, Direction.W)


def test_has_door_neighbor_opposite():
    h = House(3, 3)
    h.place_room(1, 1, Room("A", Direction(0)))
    h.place_room(2, 1, Room("B", Direction.W))
    r = h.get_room(1, 1)
    assert has_door(h, r, 1, 1, Direction.E)


def test_render_text_empty():
    h = House(1, 1)
    assert render_text(h) == "<empty house>"


def test_render_text_single_room():
    h = House(3, 3)
    h.place_room(1, 1, Room("A", Direction(0)))
    out = render_text(h)
    assert "A" in out
    assert "┌" in out
    assert "┐" in out


def test_render_text_entrance_double_border():
    h = House(3, 3)
    h.place_room(1, 1, Room("G", Direction(0)))
    out = render_text(h, entrance_pos=(1, 1))
    assert "╔" in out


def test_render_text_labels_shown():
    h = House(3, 3)
    h.place_room(0, 0, Room("A", Direction(0)))
    h.place_room(1, 0, Room("B", Direction(0)))
    out = render_text(h, show_labels=True)
    assert "0" in out
    assert "1" in out


def test_render_text_labels_hidden():
    h = House(3, 3)
    h.place_room(1, 1, Room("A", Direction(0)))
    out = render_text(h, show_labels=False)
    assert not any(c.isdigit() for c in out.split("\n")[0])


def test_render_text_empty_shown():
    h = House(3, 3)
    h.place_room(1, 0, Room("A", Direction(0)))
    h.place_room(1, 2, Room("B", Direction(0)))
    out = render_text(h, show_empty=True)
    assert "\u00b7" in out


def test_render_text_empty_hidden():
    h = House(3, 3)
    h.place_room(1, 1, Room("A", Direction(0)))
    out = render_text(h, show_empty=False)
    assert "\u00b7" not in out


def test_render_side_by_side_single():
    h = House(3, 3)
    h.place_room(1, 1, Room("A", Direction(0)))
    out = render_side_by_side([h])
    assert "A" in out
    assert "┌" in out


def test_render_side_by_side_two():
    h1 = House(3, 3)
    h1.place_room(1, 1, Room("A", Direction(0)))
    h2 = House(3, 3)
    h2.place_room(1, 1, Room("B", Direction(0)))
    out = render_side_by_side([h1, h2])
    assert "A" in out
    assert "B" in out


def test_render_side_by_side_legend_on_last_lone():
    h1 = House(3, 3)
    h1.place_room(1, 1, Room("A", Direction(0)))
    h2 = House(3, 3)
    h2.place_room(1, 1, Room("B", Direction(0)))
    out = render_side_by_side([h1, h2], cols=3, legend=["X = TestRoom"])
    assert "X = TestRoom" in out


def test_calc_cols_empty():
    assert calc_cols([], 80) == 1


def test_calc_cols_single():
    assert calc_cols([(1, 1)], 80) == 1


def test_calc_cols_two_fit():
    assert calc_cols([(1, 1), (1, 1)], 20) == 2


def test_calc_cols_only_one():
    assert calc_cols([(10, 1), (10, 1)], 20) == 1


def test_legend_entries_single():
    h = House(3, 3)
    h.place_room(1, 1, Room("Kitchen", Direction(0), legend="K"))
    entries = legend_entries(h)
    assert entries == {"K": {"Kitchen"}}


def test_legend_entries_merged():
    h = House(3, 3)
    h.place_room(0, 0, Room("Garden", Direction(0), legend="G"))
    h.place_room(
        1,
        0,
        Room("FormalGarden", Direction(0), legend="G", display_name="Formal garden"),
    )
    entries = legend_entries(h)
    assert "G" in entries
    assert "Garden" in entries["G"]
    assert "Formal garden" in entries["G"]


def test_legend_entries_no_symbol():
    h = House(3, 3)
    h.place_room(0, 0, Room("", Direction(0), legend=""))
    assert legend_entries(h) == {}


def test_format_legend():
    entries = {"A": {"Achievement gallery"}, "B": {"Bedroom"}}
    lines = format_legend(entries)
    assert lines == ["A = Achievement gallery", "B = Bedroom"]


def test_format_legend_multi():
    entries = {"G": {"Garden", "Formal garden"}}
    lines = format_legend(entries)
    assert "G = " in lines[0]
    assert "Garden" in lines[0]
    assert "Formal garden" in lines[0]


def test_format_legend_empty():
    assert format_legend({}) == []


def test_layout_dims_single():
    h = House(3, 3)
    h.place_room(1, 1, Room("A", Direction(0)))
    assert layout_dims(h) == (1, 1)


def test_layout_dims_span():
    h = House(5, 5)
    h.place_room(0, 0, Room("A", Direction(0)))
    h.place_room(2, 1, Room("B", Direction(0)))
    assert layout_dims(h) == (3, 2)


def test_layout_dims_empty():
    assert layout_dims(House(1, 1)) == (0, 0)


def test_adjacency_count_two():
    h = House(3, 3)
    h.place_room(1, 1, Room("A", Direction(0)))
    h.place_room(2, 1, Room("B", Direction(0)))
    assert adjacency_count(h) == 1


def test_adjacency_count_square():
    h = House(3, 3)
    for x in range(2):
        for y in range(2):
            h.place_room(x, y, Room("A", Direction(0)))
    assert adjacency_count(h) == 4


def test_adjacency_count_disconnected():
    h = House(5, 5)
    h.place_room(0, 0, Room("A", Direction(0)))
    h.place_room(3, 3, Room("B", Direction(0)))
    assert adjacency_count(h) == 0


def test_near_entrance_dist_zero():
    h = House(3, 3)
    h.place_room(1, 1, Room("Kitchen", Direction(0)))
    assert near_entrance_dist(h, (1, 1), {"Kitchen"}) == 0


def test_near_entrance_dist_two():
    h = House(5, 5)
    h.place_room(3, 3, Room("Kitchen", Direction(0)))
    assert near_entrance_dist(h, (1, 1), {"Kitchen"}) == 4


def test_near_entrance_dist_multiple():
    h = House(5, 5)
    h.place_room(1, 1, Room("Kitchen", Direction(0)))
    h.place_room(3, 3, Room("PortalChamber", Direction(0)))
    assert near_entrance_dist(h, (1, 1), {"Kitchen", "PortalChamber"}) == 4
