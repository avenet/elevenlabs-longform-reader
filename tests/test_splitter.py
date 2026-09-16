from app.services.splitter import split_text


def test_splits_at_paragraph_boundaries():
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    sections = split_text(text, target_chars=40, max_chars=60)
    assert len(sections) >= 2
    assert "First paragraph." in sections[0]
    assert any("Second paragraph." in section for section in sections)


def test_keeps_heading_with_following_content():
    text = "Chapter 1\n\nThe opening scene continues here."
    sections = split_text(text, target_chars=200, max_chars=300)
    assert len(sections) == 1
    assert sections[0].startswith("Chapter 1")
    assert "opening scene" in sections[0]


def test_respects_section_max_chars():
    paragraphs = [f"Paragraph {i} with enough words to fill space." for i in range(20)]
    text = "\n\n".join(paragraphs)
    max_chars = 80
    sections = split_text(text, target_chars=50, max_chars=max_chars)
    assert sections
    assert all(len(section) <= max_chars for section in sections)


def test_splits_oversized_paragraph_safely():
    sentence = "This is a long sentence that keeps going. "
    oversized = sentence * 50
    max_chars = 100
    sections = split_text(oversized, target_chars=80, max_chars=max_chars)
    assert len(sections) > 1
    assert all(len(section) <= max_chars for section in sections)


def test_splits_oversized_sentence_by_hard_cut():
    oversized = "a" * 250
    max_chars = 100
    sections = split_text(oversized, target_chars=80, max_chars=max_chars)
    assert len(sections) == 3
    assert all(len(section) <= max_chars for section in sections)


def test_empty_and_whitespace_input():
    assert split_text("") == []
    assert split_text("   \n\n\t  ") == []
