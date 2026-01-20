#ifndef GRAPHICS_H
#define GRAPHICS_H

#include <SFML/Graphics.hpp>

class MainWindow;

class Graphics
{
public:
    Graphics( MainWindow& wnd );
    ~Graphics();
    void BeginFrame();
    void EndFrame();
    void PutPixel( int x, int y, int r, int g, int b );
    
private:
    MainWindow& wnd;
    sf::RenderWindow& window;
};

#endif
