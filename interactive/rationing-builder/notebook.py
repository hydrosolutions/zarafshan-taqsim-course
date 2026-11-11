"""Build the rationing model with blocks: step 3 of the course (notebook 02) without writing code.

Run it locally (marimo and anywidget are added for the run only):

    uv run --with marimo --with anywidget marimo run interactive/rationing-builder/notebook.py

Export it for the site with `python scripts/export_rationing_builder.py`.
"""

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full", app_title="Build a TaqSim model with blocks")


@app.cell
async def _():
    import sys

    import marimo as mo

    if sys.platform == "emscripten":
        import micropip
        from pyodide_js import loadPackage

        # Pyodide's compiled scientific packages, then our pure Python wheels from beside the page
        await loadPackage(["numpy", "pandas", "matplotlib", "networkx"])
        await micropip.install(["joblib==1.5.2", "ctrl-freak==0.1.0"], deps=False)
        await micropip.install("anywidget")
        await micropip.install(
            [
                str(mo.notebook_location() / "wheels" / "taqsim-0.1.4-py3-none-any.whl"),
                str(mo.notebook_location() / "wheels" / "zarafshan_taqsim-0.1.0+wasm.builder-py3-none-any.whl"),
            ],
            deps=False,
        )

    import matplotlib

    matplotlib.use("Agg")

    from zarafshan_taqsim.block_editor import BlockEditor

    return BlockEditor, mo


@app.cell
def _(BlockEditor, mo):
    _lang = (mo.query_params().get("lang") or "en").lower()
    editor = mo.ui.anywidget(BlockEditor(lang=_lang if _lang in ("en", "ru", "uz") else "en"))
    editor
    return (editor,)


if __name__ == "__main__":
    app.run()
