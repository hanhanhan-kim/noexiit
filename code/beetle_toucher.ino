// This example shows basic use of a Pololu High Power Stepper Motor Driver.
//
// It shows how to initialize the driver, configure various settings, and enable
// the driver.  It shows how to send pulses to the STEP pin to step the motor
// and how to switch directions using the DIR pin.
//
// Before using this example, be sure to change the setCurrentMilliamps36v4 line
// to have an appropriate current limit for your system.  Also, see this
// library's documentation for information about how to connect the driver:
//   http://pololu.github.io/high-power-stepper-driver

#include <SPI.h>
#include <HighPowerStepperDriver.h>
#include <Servo.h>
# include <AccelStepper.h>

const uint8_t DirPin = 2;
const uint8_t StepPin = 3;
const uint8_t CSPin = 4;

// This period is the length of the delay between steps, which controls the
// stepper motor's speed.  You can increase the delay to make the stepper motor
// go slower.  If you decrease the delay, the stepper motor will go faster, but
// there is a limit to how fast it can go before it starts missing steps.
const uint16_t StepPeriodUs = 2000;
unsigned int stepper_pos = 6000;

// LIN ACT:
Servo myservo;  // create servo object to control a servo
int servo_pos = 0;    // variable to store the servo position
//

HighPowerStepperDriver sd;

void setup()
{
  SPI.begin();
  sd.setChipSelectPin(CSPin);

  // Drive the STEP and DIR pins low initially.
  pinMode(StepPin, OUTPUT);
  digitalWrite(StepPin, LOW);
  pinMode(DirPin, OUTPUT);
  digitalWrite(DirPin, LOW);

  // Give the driver some time to power up.
  delay(1);

  // Reset the driver to its default settings and clear latched status
  // conditions.
  sd.resetSettings();
  sd.clearStatus();

  // Select auto mixed decay.  TI's DRV8711 documentation recommends this mode
  // for most applications, and we find that it usually works well.
  sd.setDecayMode(HPSDDecayMode::AutoMixed);

  // Set the current limit. You should change the number here to an appropriate
  // value for your particular system.
  sd.setCurrentMilliamps36v4(2400);

  // Set the number of microsteps that correspond to one full step.
  sd.setStepMode(HPSDStepMode::MicroStep16);

  // Enable the motor outputs.
  sd.enableDriver();

  // LIN ACT: Attach the servo on pin 9 to the servo object
  myservo.attach(9);
}

void loop()
{
  // Step the stepper motor in the default direction n times
  setDirection(0); 
  if (unsigned int x >= 0 and x < stepper_pos)
  {
    step();
    delayMicroseconds(StepPeriodUs);
  }
  delay(300);
  /*
  // Step the stepper motor in the opposite direction n times
  setDirection(1); 
  if (unsigned int x >= 0 and x < stepper_pos)
  {
    step();
    delayMicroseconds(StepPeriodUs);
  }
  delay(300);
  */
  // Extend the lienar actuator if in bounds, retract if out of bounds:
  if (servo_pos <= 0 and servo_pos >= 100)
  {
    myservo.write(0);
    delay(15);
  }
  else 
  {
    myservo.write(101);
    delay(15);
  }
  
  /*
  // Step in the default direction 6000 times.
  setDirection(0);
  for(unsigned int x = 0; x < 6000; x++)
  {
    step();
    delayMicroseconds(StepPeriodUs);
  }

  // Wait for 300 ms.
  delay(300);

  // Step in the other direction 6000 times.
  setDirection(1);
  for(unsigned int x = 0; x < 6000; x++)
  {
    step();
    delayMicroseconds(StepPeriodUs);
  }

  // Wait for 300 ms.
  delay(300);

  // LIN ACT
  for (servo_pos = 0; servo_pos <= 180; servo_pos += 1) { // goes from 0 degrees to 180 degrees
    // in steps of 1 degree
    myservo.write(servo_pos);              // tell servo to go to position in variable 'pos'
    delay(15);                       // waits 15ms for the servo to reach the position
  }
  for (servo_pos = 180; servo_pos >= 0; servo_pos -= 1) { // goes from 180 degrees to 0 degrees
    myservo.write(servo_pos);              // tell servo to go to position in variable 'pos'
    delay(15);                       // waits 15ms for the servo to reach the position
  }
  */
}


// Sends a pulse on the STEP pin to tell the driver to take one step, and also
//delays to control the speed of the motor.
void step()
{
  // The STEP minimum high pulse width is 1.9 microseconds.
  digitalWrite(StepPin, HIGH);
  delayMicroseconds(3);
  digitalWrite(StepPin, LOW);
  delayMicroseconds(3);
}

// Writes a high or low value to the direction pin to specify what direction to
// turn the motor.
void setDirection(bool dir)
{
  // The STEP pin must not change for at least 200 nanoseconds before and after
  // changing the DIR pin.
  delayMicroseconds(1);
  digitalWrite(DirPin, dir);
  delayMicroseconds(1);
}
