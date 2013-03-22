#!/usr/bin/env python

import numpy as np
import unittest
import os
import shutil
import tempfile
import contextlib
from meld import vault, comm
from meld.remd import master_runner, ladder, adaptor
from meld.system import state


@contextlib.contextmanager
def in_temp_dir():
    try:
        cwd = os.getcwd()
        tmpdir = tempfile.mkdtemp()
        os.chdir(tmpdir)
        yield

    finally:
        os.chdir(cwd)
        shutil.rmtree(tmpdir)


class DataStorePickleTestCase(unittest.TestCase):
    '''
    Test that we can read and write the items that are pickled into the Data directory.
    '''
    def setUp(self):
        self.N_ATOMS = 500
        self.N_SPRINGS = 100
        self.N_REPLICAS = 4

    def test_init_mode_w_creates_directories(self):
        "calling initialize should create the Data and Data/Backup directories"
        with in_temp_dir():
            store = vault.DataStore(self.N_ATOMS, self.N_SPRINGS, self.N_REPLICAS)
            store.initialize(mode='new')

            self.assertTrue(os.path.exists('Data'), 'Data directory does not created')
            self.assertTrue(os.path.exists('Data/Backup'), 'Backup directory not created')

    def test_init_mode_w_creates_results(self):
        "calling initialize should create the results.h5 file"
        with in_temp_dir():
            store = vault.DataStore(self.N_ATOMS, self.N_SPRINGS, self.N_REPLICAS)
            store.initialize(mode='new')

            self.assertTrue(os.path.exists('Data/results.h5'), 'results.h5 not created')

    def test_init_mode_w_raises_when_dirs_exist(self):
        "calling initialize should raise RuntimeError when Data and Data/Backup directories exist"
        with in_temp_dir():
            os.mkdir('Data')
            os.mkdir('Data/Backup')
            store = vault.DataStore(self.N_ATOMS, self.N_SPRINGS, self.N_REPLICAS)

            with self.assertRaises(RuntimeError):
                store.initialize(mode='new')

    def test_save_and_load_data_store(self):
        "should be able to save and then reload the DataStore"
        with in_temp_dir():
            store = vault.DataStore(self.N_ATOMS, self.N_SPRINGS, self.N_REPLICAS)
            store.initialize(mode='new')

            store.save_data_store()
            store2 = vault.DataStore.load_data_store()

            self.assertEqual(store.n_atoms, store2.n_atoms)
            self.assertEqual(store.n_springs, store2.n_springs)
            self.assertEqual(store.n_replicas, store2.n_replicas)
            self.assertIsNone(store2._h5_file)
            self.assertTrue(os.path.exists('Data/data_store.dat'))

    def test_save_and_load_communicator(self):
        "should be able to save and reload the communicator"
        with in_temp_dir():
            store = vault.DataStore(self.N_ATOMS, self.N_SPRINGS, self.N_REPLICAS)
            store.initialize(mode='new')
            c = comm.MPICommunicator(self.N_ATOMS, self.N_REPLICAS, self.N_SPRINGS)
            # set _mpi_comm to something
            # this should not be saved
            c._mpi_comm = 'foo'

            store.save_communicator(c)
            c2 = store.load_communicator()

            self.assertEqual(c.n_atoms, c2.n_atoms)
            self.assertEqual(c.n_springs, c2.n_springs)
            self.assertEqual(c.n_replicas, c2.n_replicas)
            self.assertIsNone(c2._mpi_comm, '_mpi_comm should not be saved')
            self.assertTrue(os.path.exists('Data/communicator.dat'))

    def test_save_and_load_remd_runner(self):
        "should be able to save and reload an remd runner"
        with in_temp_dir():
            store = vault.DataStore(self.N_ATOMS, self.N_SPRINGS, self.N_REPLICAS)
            store.initialize(mode='new')
            l = ladder.NearestNeighborLadder(n_trials=100)
            policy = adaptor.AdaptationPolicy(1.0, 50, 100)
            a = adaptor.EqualAcceptanceAdaptor(n_replicas=self.N_REPLICAS, adaptation_policy=policy)
            runner = master_runner.MasterReplicaExchangeRunner(self.N_REPLICAS, max_steps=100, ladder=l, adaptor=a)

            store.save_remd_runner(runner)
            runner2 = store.load_remd_runner()

            self.assertEqual(runner.n_replicas, runner2.n_replicas)
            self.assertTrue(os.path.exists('Data/remd_runner.dat'))


class DataStoreHD5TestCase(unittest.TestCase):
    '''
    Test that we can read and write the data that goes in the hd5 file.
    '''
    def setUp(self):
        # create and change to temp dir
        self.cwd = os.getcwd()
        self.tmpdir = tempfile.mkdtemp()
        os.chdir(self.tmpdir)

        # setup data store
        self.N_ATOMS = 500
        self.N_REPLICAS = 16
        self.N_SPRINGS = 100
        self.store = vault.DataStore(self.N_ATOMS, self.N_SPRINGS, self.N_REPLICAS)
        self.store.initialize(mode='new')

    def tearDown(self):
        # switch to original dir and clean up
        os.chdir(self.cwd)
        shutil.rmtree(self.tmpdir)

    def test_can_save_and_load_positions(self):
        "should be able to save and load positions"
        test_pos = np.zeros((self.N_REPLICAS, self.N_ATOMS, 3))
        for i in range(self.N_REPLICAS):
            test_pos[i, :, :] = i

        STAGE = 0
        self.store.save_positions(test_pos, STAGE)
        self.store.save_data_store()
        self.store.close()
        store2 = vault.DataStore.load_data_store()
        store2.initialize(mode='existing')
        test_pos2 = store2.load_positions(STAGE)

        np.testing.assert_equal(test_pos, test_pos2)

    def test_can_save_and_load_velocities(self):
        "should be able to save and load velocities"
        test_vel = np.zeros((self.N_REPLICAS, self.N_ATOMS, 3))
        for i in range(self.N_REPLICAS):
            test_vel[i, :, :] = i

        STAGE = 0
        self.store.save_velocities(test_vel, STAGE)
        self.store.save_data_store()
        self.store.close()
        store2 = vault.DataStore.load_data_store()
        store2.initialize(mode='existing')
        test_vel2 = store2.load_velocities(STAGE)

        np.testing.assert_equal(test_vel, test_vel2)

    def test_can_save_and_load_spring_states(self):
        "should be able to save and load spring_states"
        test_springs = np.zeros((self.N_REPLICAS, self.N_SPRINGS))
        for i in range(self.N_REPLICAS):
            test_springs[i, :] = i % 2

        STAGE = 0
        self.store.save_spring_states(test_springs, STAGE)
        self.store.save_data_store()
        self.store.close()
        store2 = vault.DataStore.load_data_store()
        store2.initialize(mode='existing')
        test_springs2 = store2.load_spring_states(STAGE)

        np.testing.assert_equal(test_springs, test_springs2)

    def test_can_save_and_load_lambdas(self):
        "should be able to save and load lambdas"
        test_lambdas = np.zeros(self.N_REPLICAS)
        for i in range(self.N_REPLICAS):
            test_lambdas[i] = i / (self.N_REPLICAS - 1)

        STAGE = 0
        self.store.save_lambdas(test_lambdas, STAGE)
        self.store.save_data_store()
        self.store.close()
        store2 = vault.DataStore.load_data_store()
        store2.initialize(mode='existing')
        test_lambdas2 = store2.load_lambdas(STAGE)

        np.testing.assert_equal(test_lambdas, test_lambdas2)

    def test_can_save_and_load_energies(self):
        "should be able to save and load energies"
        test_energies = np.zeros(self.N_REPLICAS)
        for i in range(self.N_REPLICAS):
            test_energies[i] = i

        STAGE = 0
        self.store.save_energies(test_energies, STAGE)
        self.store.save_data_store()
        self.store.close()
        store2 = vault.DataStore.load_data_store()
        store2.initialize(mode='existing')
        test_energies2 = store2.load_energies(STAGE)

        np.testing.assert_equal(test_energies, test_energies2)

    def test_can_save_and_load_spring_energies(self):
        "should be able to save and load spring_energies"
        test_spring_energies = np.zeros((self.N_REPLICAS, self.N_SPRINGS))
        for i in range(self.N_REPLICAS):
            test_spring_energies[i, :] = i

        STAGE = 0
        self.store.save_spring_energies(test_spring_energies, STAGE)
        self.store.save_data_store()
        self.store.close()
        store2 = vault.DataStore.load_data_store()
        store2.initialize(mode='existing')
        test_spring_energies2 = store2.load_spring_energies(STAGE)

        np.testing.assert_equal(test_spring_energies, test_spring_energies2)

    def test_can_save_and_load_states(self):
        "should be able to save and load states"
        def gen_state(index, n_atoms, n_springs):
            pos = index * np.ones((n_atoms, 3))
            vel = index * np.ones((n_atoms, 3))
            ss = index * np.ones(n_springs)
            se = index * np.ones(n_springs)
            energy = index
            lam = index / 100.
            return state.SystemState(pos, vel, ss, lam, energy, se)

        states = [gen_state(i, self.N_ATOMS, self.N_SPRINGS) for i in range(self.N_REPLICAS)]
        STAGE = 0

        self.store.save_states(states, STAGE)
        self.store.save_data_store()
        self.store.close()
        store2 = vault.DataStore.load_data_store()
        store2.initialize(mode='existing')
        states2 = store2.load_states(STAGE)

        np.testing.assert_equal(states[-1].positions, states2[-1].positions)


class DataStoreBackupTestCase(unittest.TestCase):
    '''
    Test that backup files are created/copied correctly.
    '''
    def setUp(self):
        # create and change to temp dir
        self.cwd = os.getcwd()
        self.tmpdir = tempfile.mkdtemp()
        os.chdir(self.tmpdir)

        self.N_ATOMS = 500
        self.N_REPLICAS = 16
        self.N_SPRINGS = 100

        # setup objects to save to disk
        c = comm.MPICommunicator(self.N_ATOMS, self.N_REPLICAS, self.N_SPRINGS)

        l = ladder.NearestNeighborLadder(n_trials=100)
        policy = adaptor.AdaptationPolicy(1.0, 50, 100)
        a = adaptor.EqualAcceptanceAdaptor(n_replicas=self.N_REPLICAS, adaptation_policy=policy)

        # make some states
        def gen_state(index, n_atoms, n_springs):
            pos = index * np.ones((n_atoms, 3))
            vel = index * np.ones((n_atoms, 3))
            ss = index * np.ones(n_springs)
            se = index * np.ones(n_springs)
            energy = index
            lam = index / 100.
            return state.SystemState(pos, vel, ss, lam, energy, se)

        states = [gen_state(i, self.N_ATOMS, self.N_SPRINGS) for i in range(self.N_REPLICAS)]
        runner = master_runner.MasterReplicaExchangeRunner(self.N_REPLICAS, max_steps=100, ladder=l, adaptor=a)

        self.store = vault.DataStore(self.N_ATOMS, self.N_SPRINGS, self.N_REPLICAS)
        self.store.initialize(mode='new')

        # save some stuff
        self.store.save_data_store()
        self.store.save_communicator(c)
        self.store.save_remd_runner(runner)
        self.store.save_states(states, stage=0)

    def tearDown(self):
        # switch to original dir and clean up
        os.chdir(self.cwd)
        shutil.rmtree(self.tmpdir)

    def test_backup_copies_comm(self):
        "communicator.dat should be backed up"
        self.store.backup(stage=0)

        self.assertTrue(os.path.exists('Data/Backup/communicator.dat'))

    def test_backup_copies_store(self):
        "data_store.dat should be backed up"
        self.store.backup(stage=0)

        self.assertTrue(os.path.exists('Data/Backup/data_store.dat'))

    def test_backup_copies_remd_runner(self):
        "remd_runner.dat should be backed up"
        self.store.backup(stage=0)

        self.assertTrue(os.path.exists('Data/Backup/remd_runner.dat'))

    def test_backup_copies_h5(self):
        "results.h5 should be backed up"
        self.store.backup(stage=0)

        self.assertTrue(os.path.exists('Data/Backup/results.h5'))
        # make sure we can still access the hd5 file after backup
        states = self.store.load_states(stage=0)


def main():
    unittest.main()


if __name__ == '__main__':
    main()
