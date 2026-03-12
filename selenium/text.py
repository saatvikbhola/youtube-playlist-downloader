import pyfiglet 
from rich.console import Console
from rich.text import Text


def print_gradient_logo(text, font="slant", start_color=(255, 0, 255), end_color=(0, 255, 255)):
    """
    Prints ASCII text with a true-color gradient (RGB interpolation).
    """
    ascii_art = pyfiglet.figlet_format(text, font=font)
    lines = ascii_art.splitlines()
    console = Console()
    
    # Calculate how many lines we have to spread the gradient over
    height = len(lines)
    
    for i, line in enumerate(lines):
        # Calculate interpolation factor (0.0 to 1.0)
        t = i / max(1, height - 1)
        
        # Interpolate RGB values
        r = int(start_color[0] + (end_color[0] - start_color[0]) * t)
        g = int(start_color[1] + (end_color[1] - start_color[1]) * t)
        b = int(start_color[2] + (end_color[2] - start_color[2]) * t)
        
        # Create styled text for this line
        color_hex = f"#{r:02x}{g:02x}{b:02x}"
        styled_line = Text(line, style=color_hex)
        console.print(styled_line)

# Example Usage
print_gradient_logo("YouTube\nDownloader", font="block")
