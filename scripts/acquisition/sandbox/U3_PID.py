#!/home/platyusa/anaconda3/envs/behaviour/bin/python

import u3

d = u3.U3()
import ipdb; ipdb.set_trace()

d.eioAnalog

# possible fns to use:
# - getAIN
# - configAnalog
# - getFeedback
# - streamConfig

print(d.configU3())


d.close()