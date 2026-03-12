from rich import print
from rich.layout import Layout

layout=Layout(name="root")

layout.split(
    Layout(name="root",size=7),
    Layout(name="main",size=30),
    Layout(name="Progress",size=9)
)

layout["main"].split_row(
    Layout(name="left"),
    Layout(name="Logs") 
)

layout["left"].split_column(
    Layout(name="inputs"),
    Layout(name="saved to folder")
)


print(layout)
