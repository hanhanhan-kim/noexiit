// Set the current limit to 2400 mA.
// Documentation: http://pololu.github.io/high-power-stepper-driver

// SET-UP -----------------------------------------------------------------------

#include <Servo.h>
#include <SPI.h>
#include <HighPowerStepperDriver.h>

// Servo pin:
const uint8_t servo_pin = 9;
// Stepper pins:
const uint8_t dir_pin = 2;
const uint8_t step_pin = 3;
const uint8_t cs_pin = 4;

// Initialize my servo as a servo:
Servo myservo;
// Initialize my stepper as a high-powered stepper:
HighPowerStepperDriver sd;

// Initialize my servo pos as position 0;
int pos = 0;

// This period is the length of the delay between steps, which controls the
// stepper motor's speed.  You can increase the delay to make the stepper motor
// go slower.  If you decrease the delay, the stepper motor will go faster, but
// there is a limit to how fast it can go before it starts missing steps.
const uint16_t StepPeriodUs = 200;

// FUNCTIONS -----------------------------------------------------------------------

// Sends a pulse on the STEP pin to tell the driver to take one step, and also
//delays to control the speed of the motor.
void step()
{
  // The STEP minimum high pulse width is 1.9 microseconds.
  digitalWrite(step_pin, HIGH);
  delayMicroseconds(3);
  digitalWrite(step_pin, LOW);
  delayMicroseconds(3);
}

// Writes a high or low value to the direction pin to specify what direction to
// turn the motor.
void setDirection(bool dir)
{
  // The STEP pin must not change for at least 200 nanoseconds before and after
  // changing the DIR pin.
  delayMicroseconds(1);
  digitalWrite(dir_pin, dir);
  delayMicroseconds(1);
}

// RUN ONCE ------------------------------------------------------------------------
void setup()
{
  // Attach the servo to the servo pin.
  myservo.attach(servo_pin);

  SPI.begin();
  sd.setChipSelectPin(cs_pin);

  // Initialize the STEP and DIR pins to low.
  pinMode(step_pin, OUTPUT);
  digitalWrite(step_pin, LOW);
  pinMode(dir_pin, OUTPUT);
  digitalWrite(dir_pin, LOW);

  // Give the driver 1 ms to power up.
  delay(1);

  // Reset the driver to its default settings and clear latched status conditions.
  sd.resetSettings();
  sd.clearStatus();

  // Select auto mixed decay.  TI's DRV8711 documentation recommends the auto mixed decay mode.
  sd.setDecayMode(HPSDDecayMode::AutoMixed);

  // Set the current limit.
  sd.setCurrentMilliamps36v4(2400);

  // Set the number of microsteps that corresponds to one full step.
  sd.setStepMode(HPSDStepMode::MicroStep32);

  // Enable the motor outputs.
  sd.enableDriver();
}

// RUN INFINITELY -------------------------------------------------------------------
void loop()
{ 
  /*
  setDirection(false);
  for (unsigned long i = 0; i <= 30720; i++) //under MicroStep32, 30720 is full revo
  {
     step();
     delayMicroseconds(StepPeriodUs);
  }
  
  delay(500);

  setDirection(true);
  for (unsigned long i = 0; i <= 5120; i++)
  {
     step();
     delayMicroseconds(StepPeriodUs);
  }
  
  delay(500);

  setDirection(false);
  for (unsigned long i = 0; i <= 10240; i++)
  {
    step();
    delayMicroseconds(StepPeriodUs);
  }

  delay(500);

  setDirection(true);
  for (unsigned long i = 0; i <= 5120; i++)
  {
    step();
    delayMicroseconds(StepPeriodUs);
  }
  

  */
  // Extend the linear actuator back and forth:
  for (pos = 0; pos <= 180; pos += 1) { // goes from 0 degrees to 180 degrees
    // in steps of 1 degree
    myservo.write(pos);              // tell servo to go to position in variable 'pos'
    delay(15);                       // waits 15ms for the servo to reach the position
  }
  
  
  for (pos = 180; pos >= 0; pos -= 1) { // goes from 180 degrees to 0 degrees
    myservo.write(pos);              // tell servo to go to position in variable 'pos'
    delay(15);                       // waits 15ms for the servo to reach the position
  }

  delay(8000);

}
