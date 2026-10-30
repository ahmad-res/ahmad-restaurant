if __package__:
    from .command_center import JarvisWindow
else:
    from command_center import JarvisWindow

__all__ = ["JarvisWindow"]