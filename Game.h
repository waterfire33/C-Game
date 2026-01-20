#ifndef GAME_H
#define GAME_H

#include "Graphics.h"

class MainWindow;

class Game
{
public:
    Game( MainWindow& wnd );
    ~Game();
    void Go();
    
private:
    void UpdateModel();
    void ComposeFrame();
    
private:
    MainWindow& wnd;
    Graphics gfx;
};

#endif
