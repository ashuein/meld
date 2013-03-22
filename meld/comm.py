import numpy as np


class MPICommunicator(object):
    '''
    Class to handle communications between master and slaves using MPI

    '''
    def __init__(self, n_atoms, n_replicas, n_springs):
        '''
        Create an MPICommunicator

        Parameters
            n_atoms -- number of atoms
            n_replicas -- number of replicas
            n_springs -- number of springs

        Note: creating an MPI communicator will not actually initialize MPI. To do that,
        call initialize().

        '''
        # We're not using n_atoms, n_replicas, and n_springs, but if we switch
        # to more efficient buffer-based MPI routines, we'll need them.
        self._n_atoms = n_atoms
        self._n_replicas = n_replicas
        self._n_springs = n_springs
        self._mpi_comm = None

    def __getstate__(self):
        # don't pickle _mpi_comm
        return dict((k, v) for (k, v) in self.__dict__.iteritems() if not k == '_mpi_comm')

    def __setstate__(self, state):
        # set _mpi_comm to None
        self.__dict__ = state
        self._mpi_comm = None

    def initialize(self):
        '''
        Initialize and start MPI

        '''
        self._mpi_comm = get_mpi_comm_world()
        self._my_rank = self._mpi_comm.Get_rank()

    def is_master(self):
        '''
        Is this the master node?

        Returns
            True if we are the master, otherwise False

        '''
        if self._my_rank == 0:
            return True
        else:
            return False

    def broadcast_lambdas_to_slaves(self, lambdas):
        '''
        Send the lambda values to the slaves

        Parameters
            lambdas -- a list of lambda values, one for each replica
        Returns
            None

        The master node's lambda value should be included in this list.
        The master node will always be at lambda=0.0

        '''
        self._mpi_comm.scatter(lambdas, root=0)

    def recieve_lambda_from_master(self):
        '''
        Recieve lambda value from master node

        Returns
            a floating point value for lambda in [0,1]

        '''
        return self._mpi_comm.scatter(None, root=0)

    def broadcast_states_to_slaves(self, states):
        '''
        Send a state to each slave

        Parameters
            states -- a list of states
        Returns
            the state to run on the master node

        The list of states should include the state for the master node. These are the
        states that will be simulated on each replica for each step.

        '''
        return self._mpi_comm.scatter(states, root=0)

    def recieve_state_from_master(self):
        '''
        Get state to run for this step

        Returns
            the state to run for this step

        '''
        return self._mpi_comm.scatter(None, root=0)

    def gather_states_from_slaves(self, state_on_master):
        '''
        Recieve states from all slaves

        Parameters
            state_on_master -- the state on the master after simulating
        Returns
            a list of states, one from each replica

        The returned states are the states after simulating.

        '''
        return self._mpi_comm.gather(state_on_master, root=0)

    def send_state_to_master(self, state):
        '''
        Send state to master

        Parameters
            state -- state to send to master
        Returns
            None

        This is the state after simulating this step.

        '''
        self._mpi_comm.gather(state, root=0)

    def broadcast_states_for_energy_calc_to_slaves(self, states):
        '''
        Broadcast states to all slaves

        Parameters
            states -- a list of states
        Returns
            None

        Send all results from this step to every slave so that we can calculate
        the energies and do replica exchange.

        '''
        self._mpi_comm.bcast(states, root=0)

    def recieve_states_for_energy_calc_from_master(self):
        '''
        Recieve all states from master

        Returns
            a list of states to calculate the energy of

        '''
        return self._mpi_comm.bcast(None, root=0)

    def gather_energies_from_slaves(self, energies_on_master):
        '''
        Recieve a list of energies from each slave

        Parameters
            energies_on_master -- a list of energies from the master
        Returns
            a square matrix of every state on every replica to be used for replica exchange

        '''
        energies = self._mpi_comm.gather(energies_on_master, root=0)
        return np.array(energies)

    def send_energies_to_master(self, energies):
        '''
        Send a list of energies to the master

        Parameters
            energies -- a list of energies to send to the master
        Returns
            None

        '''
        return self._mpi_comm.gather(energies, root=0)

    @property
    def n_replicas(self):
        return self._n_replicas

    @property
    def n_atoms(self):
        return self._n_atoms

    @property
    def n_springs(self):
        return self._n_springs

    @property
    def rank(self):
        return self._my_rank


def get_mpi_comm_world():
    '''
    Helper function to import mpi4py and return the comm_world.

    '''
    from mpi4py import MPI
    return MPI.COMM_WORLD
