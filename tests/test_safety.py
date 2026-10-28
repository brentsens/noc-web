def test_noc_root_is_temporary(
    noc_root,
):

    assert noc_root.exists()

    assert str(noc_root).startswith(
        "/tmp/"
    )

    assert str(noc_root) != (
        "/home/bsmith/noc"
    )