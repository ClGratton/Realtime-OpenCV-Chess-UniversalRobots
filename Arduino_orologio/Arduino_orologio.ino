#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128 // OLED display width, in pixels
#define SCREEN_HEIGHT 64 // OLED display height, in pixels

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT);

int button2 = 2;
int button3 = 3;
int button4 = 8;
int button5 = 5;
int button6 = 6;
int button7 = 7;

bool valueButton2;
bool valueButton3;
bool valueButton4;
bool valueButton5;
bool valueButton6;
bool valueButton7;

typedef enum {Stop, Tempo_Bianco, Tempo_Nero, Mossa_Bianco, Mossa_Nero} Stato;

Stato stati;


void setup() {
  // put your setup code here, to run once:
  pinMode(button2, INPUT_PULLUP);
  pinMode(button3, INPUT_PULLUP);
  pinMode(button4, INPUT_PULLUP);
  pinMode(button5, INPUT_PULLUP);
  pinMode(button6, INPUT_PULLUP);
  pinMode(button7, INPUT_PULLUP);
  Serial.begin(9600);


  if (!display.begin( SSD1306_SWITCHCAPVCC, 0x3C)) {
    while (true);
    
  }
    display.clearDisplay();
    display.display();

  
}



void pulsanti() {
  valueButton2 = digitalRead(button2);
  valueButton3 = digitalRead(button3);
  valueButton4 = digitalRead(button4);
  valueButton5 = digitalRead(button5);
  valueButton6 = digitalRead(button6);
  valueButton7 = digitalRead(button7);
}



void loop() {
  pulsanti();

  switch(stati) {


    case Stop:

  break;

    case Tempo_Bianco:

    break;

    case Tempo_Nero:

    break;

    case Mossa_Bianco:

    break;


    case Mossa_Nero:

    break; 
  }
  stampaPronti();
}


void stampaPronti() {
  display.clearDisplay();
  display.setTextColor( WHITE);
   display.setTextSize(1);
  display.setCursor(3, 3);
  display.println("Nero (Quello scarso)");
  display.setTextSize(3);
  display.setCursor(0, (SCREEN_HEIGHT / 2) -8);
  display.println("Pronto?");
  display.display();
}
