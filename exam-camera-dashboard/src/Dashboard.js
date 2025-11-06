import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { collection, getDocs, query, orderBy, onSnapshot } from 'firebase/firestore';
import { db, auth } from './firebase';
import { signOut } from 'firebase/auth';
import {
  Box,
  Container,
  Typography,
  Card,
  CardContent,
  Grid,
  Chip,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  CircularProgress,
  Alert,
  ImageList,
  ImageListItem,
  ImageListItemBar,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  IconButton,
  Tooltip,
  Stack,
  Badge,
  useMediaQuery,
  useTheme,
  Fade,
  Zoom
} from '@mui/material';
import {
  CameraAlt,
  Visibility,
  Close,
  Security,
  Warning,
  CheckCircle,
  Person,
  DirectionsRun,
  PhoneAndroid,
  AccessTime,
  LocationOn,
  Language,
  Sensors,
  TrendingUp,
  Refresh,
  Wifi,
  WifiOff,
  Update
} from '@mui/icons-material';
import { format } from 'date-fns';

const Dashboard = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedImage, setSelectedImage] = useState(null);
  const [imageDialogOpen, setImageDialogOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const unsubscribeRef = useRef(null);
  
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const isTablet = useMediaQuery(theme.breakpoints.down('lg'));

  useEffect(() => {
    setupRealtimeListener();
    
    // Cleanup function to unsubscribe from listener
    return () => {
      if (unsubscribeRef.current) {
        unsubscribeRef.current();
        unsubscribeRef.current = null;
      }
    };
  }, []);

  const setupRealtimeListener = () => {
    try {
      setLoading(true);
      setError(null);
      setIsConnected(false);
      
      console.log('Setting up real-time Firebase listener...');
      
      const collectionName = 'exam_alerts';
      let q;
      
      // Create query with proper error handling
      try {
        // Try with ordering first
        q = query(collection(db, collectionName), orderBy('created_at', 'desc'));
        console.log('✅ Using ordered query');
      } catch (orderError) {
        console.log('⚠️ Error with ordering, using collection without orderBy:', orderError.message);
        q = query(collection(db, collectionName));
        console.log('✅ Using unordered query');
      }
      
      // Set up real-time listener
      const unsubscribe = onSnapshot(
        q,
        (querySnapshot) => {
          console.log('✅ Real-time update received');
          setIsConnected(true);
          setLastUpdate(new Date());
          
          const documents = [];
          querySnapshot.forEach((doc) => {
            documents.push({
              id: doc.id,
              collection: collectionName,
              ...doc.data()
            });
          });
          
          console.log(`✅ Real-time update: ${documents.length} documents`);
          
          if (documents.length === 0) {
            console.log('⚠️ No documents found in collection');
            setError('No data found in exam_alerts collection. Please check: 1) Collection name is correct, 2) Firebase security rules allow read access, 3) Data exists in Firestore');
          } else {
            console.log('✅ Data loaded successfully:', documents.length, 'documents');
            setData(documents);
            setError(null);
          }
          
          setLoading(false);
          setRefreshing(false);
        },
        (error) => {
          console.error('❌ Real-time listener error:', error);
          setIsConnected(false);
          setError(`Real-time connection failed: ${error.message}. Please check your Firebase configuration and security rules.`);
          setLoading(false);
          setRefreshing(false);
        }
      );
      
      // Store unsubscribe function
      unsubscribeRef.current = unsubscribe;
      
    } catch (err) {
      console.error('❌ Error setting up real-time listener:', err);
      setError(`Failed to setup real-time listener: ${err.message}`);
      setLoading(false);
      setRefreshing(false);
    }
  };

  const fetchData = async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
      // Force a refresh by temporarily disconnecting and reconnecting
      if (unsubscribeRef.current) {
        unsubscribeRef.current();
        unsubscribeRef.current = null;
      }
      // Small delay to ensure cleanup
      setTimeout(() => {
        setupRealtimeListener();
      }, 100);
    }
  };

  const handleRefresh = useCallback(() => {
    fetchData(true);
  }, []);

  const handleImageClick = useCallback((imageUrl) => {
    setSelectedImage(imageUrl);
    setImageDialogOpen(true);
  }, []);

  const handleCloseImageDialog = useCallback(() => {
    setImageDialogOpen(false);
    setSelectedImage(null);
  }, []);

  const handleSignOut = useCallback(async () => {
    try {
      await signOut(auth);
    } catch (err) {
      console.error('Sign out failed', err);
    }
  }, []);

  const getEventChipColor = useCallback((event) => {
    if (event.includes('Turning back') || event.includes('movement')) return 'warning';
    if (event.includes('detected') || event.includes('unknown')) return 'error';
    if (event.includes('phone') || event.includes('mobile')) return 'secondary';
    return 'default';
  }, []);

  const getEventIcon = useCallback((event) => {
    if (event.includes('Turning back') || event.includes('movement')) return <DirectionsRun />;
    if (event.includes('detected') || event.includes('unknown')) return <Security />;
    if (event.includes('phone') || event.includes('mobile')) return <PhoneAndroid />;
    return <CheckCircle />;
  }, []);

  const getActionFromData = useCallback((item) => {
    const actions = [];
    if (item.events && item.events.length > 0) {
      actions.push(...item.events);
    }
    if (item.unknown_faces > 0) {
      actions.push(`${item.unknown_faces} Unknown Face${item.unknown_faces > 1 ? 's' : ''}`);
    }
    if (item.faces_detected && item.faces_detected.length > 0) {
      actions.push(`${item.faces_detected.length} Face${item.faces_detected.length > 1 ? 's' : ''} Detected`);
    }
    return actions.length > 0 ? actions.join(', ') : 'No Activity';
  }, []);

  const getActionSeverity = useCallback((item) => {
    if (item.unknown_faces > 0 || (item.events && item.events.some(e => e.includes('detected')))) {
      return 'error';
    }
    if (item.events && item.events.some(e => e.includes('movement') || e.includes('Turning'))) {
      return 'warning';
    }
    return 'success';
  }, []);

  // Memoized calculations for summary statistics
  const summaryStats = useMemo(() => {
    const totalRecords = data.length;
    const totalUnknownFaces = data.reduce((sum, item) => sum + (item.unknown_faces || 0), 0);
    const totalEvents = data.reduce((sum, item) => sum + (item.events?.length || 0), 0);
    const activeCameras = new Set(data.map(item => item.camera_id)).size;
    
    return {
      totalRecords,
      totalUnknownFaces,
      totalEvents,
      activeCameras
    };
  }, [data]);

  // Memoized filtered data for images
  const imageData = useMemo(() => {
    return data.filter(item => item.image_url);
  }, [data]);

  // Determine if any record contains a seat number to conditionally render UI
  const hasSeatNumber = useMemo(() => data.some(item => item.seat_number !== undefined && item.seat_number !== null && item.seat_number !== ''), [data]);

  if (loading) {
    return (
      <Box 
        display="flex" 
        flexDirection="column"
        justifyContent="center" 
        alignItems="center" 
        minHeight="100vh"
        sx={{ bgcolor: 'background.default' }}
      >
        <CircularProgress size={60} thickness={4} />
        <Typography variant="h6" sx={{ mt: 2, color: 'text.secondary' }}>
          Loading Exam Camera Data...
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Container maxWidth="md" sx={{ mt: 4, px: 2 }}>
        <Alert 
          severity="error" 
          sx={{ 
            borderRadius: 2,
            '& .MuiAlert-message': { fontSize: '1rem' }
          }}
        >
          {error}
        </Alert>
      </Container>
    );
  }

  return (
    <Box sx={{ bgcolor: 'background.default', minHeight: '100vh' }}>
      <Container maxWidth="xl" sx={{ py: { xs: 2, md: 4 }, px: { xs: 1, md: 2 } }}>
        {/* Header */}
        <Fade in timeout={800}>
          <Box sx={{ mb: { xs: 3, md: 4 } }}>
            <Stack 
              direction={{ xs: 'column', sm: 'row' }} 
              justifyContent="space-between" 
              alignItems={{ xs: 'flex-start', sm: 'flex-start' }}
              spacing={{ xs: 3, sm: 2 }}
            >
              <Box sx={{ width: { xs: '100%', sm: 'auto' } }}>
                <Typography 
                  variant={isMobile ? "h5" : "h4"} 
                  component="h1" 
                  sx={{ 
                    fontWeight: 700,
                    background: 'linear-gradient(45deg, #2563eb, #3b82f6)',
                    backgroundClip: 'text',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    mb: { xs: 1.5, md: 1 },
                    textAlign: { xs: 'center', sm: 'left' }
                  }}
                >
                  <CameraAlt sx={{ 
                    mr: { xs: 1, md: 2 }, 
                    verticalAlign: 'middle', 
                    fontSize: isMobile ? '1.5rem' : 'inherit' 
                  }} />
                  {isMobile ? 'Exam Dashboard' : 'Exam Camera Dashboard'}
                </Typography>
                
                <Typography 
                  variant={isMobile ? "body2" : "body1"} 
                  color="text.secondary"
                  sx={{ 
                    mb: { xs: 2, md: 1 },
                    textAlign: { xs: 'center', sm: 'left' },
                    px: { xs: 2, sm: 0 }
                  }}
                >
                  {isMobile ? 'Real-time monitoring' : 'Real-time surveillance monitoring and alert system'}
                </Typography>
                
                {/* Status Chips - Reorganized for mobile */}
                <Stack 
                  direction={{ xs: 'column', sm: 'row' }} 
                  alignItems={{ xs: 'center', sm: 'flex-start' }}
                  spacing={{ xs: 1, sm: 2 }}
                  sx={{ width: '100%' }}
                >
                  <Stack 
                    direction="row" 
                    alignItems="center" 
                    spacing={1}
                    sx={{ 
                      justifyContent: { xs: 'center', sm: 'flex-start' },
                      flexWrap: 'wrap',
                      gap: 1
                    }}
                  >
                    {isConnected ? (
                      <Chip
                        icon={<Wifi />}
                        label="Live"
                        color="success"
                        size={isMobile ? "medium" : "small"}
                        sx={{ 
                          fontWeight: 600,
                          '& .MuiChip-label': { px: isMobile ? 2 : 1 }
                        }}
                      />
                    ) : (
                      <Chip
                        icon={<WifiOff />}
                        label="Offline"
                        color="error"
                        size={isMobile ? "medium" : "small"}
                        sx={{ 
                          fontWeight: 600,
                          '& .MuiChip-label': { px: isMobile ? 2 : 1 }
                        }}
                      />
                    )}
                    {lastUpdate && (
                      <Chip
                        icon={<Update />}
                        label={isMobile ? format(lastUpdate, 'HH:mm') : `Updated ${format(lastUpdate, 'HH:mm:ss')}`}
                        variant="outlined"
                        size={isMobile ? "medium" : "small"}
                        sx={{ 
                          fontWeight: 500,
                          '& .MuiChip-label': { px: isMobile ? 2 : 1 }
                        }}
                      />
                    )}
                  </Stack>
                </Stack>
              </Box>
              
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ width: { xs: '100%', sm: 'auto' }}}>
                <Button
                  variant="outlined"
                  startIcon={!isMobile && <Refresh />}
                  onClick={handleRefresh}
                  disabled={refreshing}
                  fullWidth={isMobile}
                  sx={{ 
                    borderRadius: 2,
                    textTransform: 'none',
                    fontWeight: 600,
                    py: { xs: 1.5, md: 1 },
                    px: { xs: 3, md: 2 },
                    minHeight: { xs: 48, md: 'auto' },
                    fontSize: { xs: '1rem', md: '0.875rem' }
                  }}
                >
                  {isMobile && <Refresh sx={{ mr: 1, fontSize: '1.2rem' }} />}
                  {refreshing ? (isMobile ? 'Refreshing...' : 'Refreshing...') : (isMobile ? 'Refresh' : 'Refresh Data')}
                </Button>
                <Button
                  variant="contained"
                  color="error"
                  onClick={handleSignOut}
                  fullWidth={isMobile}
                  sx={{
                    borderRadius: 2,
                    textTransform: 'none',
                    fontWeight: 700,
                    py: { xs: 1.5, md: 1 },
                    px: { xs: 3, md: 2 },
                    minHeight: { xs: 48, md: 'auto' },
                    fontSize: { xs: '1rem', md: '0.875rem' }
                  }}
                >
                  Sign Out
                </Button>
              </Stack>
            </Stack>
          </Box>
        </Fade>

        {/* Summary Cards */}
        <Fade in timeout={1000}>
          <Grid container spacing={{ xs: 2, md: 3 }} sx={{ mb: 4 }}>
            <Grid item xs={6} sm={6} md={3}>
              <Zoom in timeout={1200}>
                <Card sx={{ 
                  height: '100%',
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  color: 'white',
                  position: 'relative',
                  overflow: 'hidden'
                }}>
                  <CardContent sx={{ p: 3 }}>
                    <Stack direction="row" alignItems="center" spacing={2}>
                      <Box sx={{ 
                        bgcolor: 'rgba(255,255,255,0.2)', 
                        borderRadius: 2, 
                        p: 1.5,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                      }}>
                        <TrendingUp sx={{ fontSize: 28 }} />
                      </Box>
                      <Box>
                        <Typography variant="body2" sx={{ opacity: 0.9, fontWeight: 500 }}>
                          Total Records
                        </Typography>
                        <Typography variant={isMobile ? "h5" : "h4"} sx={{ fontWeight: 700 }}>
                          {summaryStats.totalRecords}
                        </Typography>
                      </Box>
                    </Stack>
                  </CardContent>
                </Card>
              </Zoom>
            </Grid>
            
            <Grid item xs={6} sm={6} md={3}>
              <Zoom in timeout={1400}>
                <Card sx={{ 
                  height: '100%',
                  background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
                  color: 'white',
                  position: 'relative',
                  overflow: 'hidden'
                }}>
                  <CardContent sx={{ p: 3 }}>
                    <Stack direction="row" alignItems="center" spacing={2}>
                      <Box sx={{ 
                        bgcolor: 'rgba(255,255,255,0.2)', 
                        borderRadius: 2, 
                        p: 1.5,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                      }}>
                        <Person sx={{ fontSize: 28 }} />
                      </Box>
                      <Box>
                        <Typography variant="body2" sx={{ opacity: 0.9, fontWeight: 500 }}>
                          Unknown Faces
                        </Typography>
                        <Typography variant={isMobile ? "h5" : "h4"} sx={{ fontWeight: 700 }}>
                          {summaryStats.totalUnknownFaces}
                        </Typography>
                      </Box>
                    </Stack>
                  </CardContent>
                </Card>
              </Zoom>
            </Grid>
            
            <Grid item xs={6} sm={6} md={3}>
              <Zoom in timeout={1600}>
                <Card sx={{ 
                  height: '100%',
                  background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
                  color: 'white',
                  position: 'relative',
                  overflow: 'hidden'
                }}>
                  <CardContent sx={{ p: 3 }}>
                    <Stack direction="row" alignItems="center" spacing={2}>
                      <Box sx={{ 
                        bgcolor: 'rgba(255,255,255,0.2)', 
                        borderRadius: 2, 
                        p: 1.5,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                      }}>
                        <Warning sx={{ fontSize: 28 }} />
                      </Box>
                      <Box>
                        <Typography variant="body2" sx={{ opacity: 0.9, fontWeight: 500 }}>
                          Total Events
                        </Typography>
                        <Typography variant={isMobile ? "h5" : "h4"} sx={{ fontWeight: 700 }}>
                          {summaryStats.totalEvents}
                        </Typography>
                      </Box>
                    </Stack>
                  </CardContent>
                </Card>
              </Zoom>
            </Grid>
            
            <Grid item xs={6} sm={6} md={3}>
              <Zoom in timeout={1800}>
                <Card sx={{ 
                  height: '100%',
                  background: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
                  color: 'white',
                  position: 'relative',
                  overflow: 'hidden'
                }}>
                  <CardContent sx={{ p: 3 }}>
                    <Stack direction="row" alignItems="center" spacing={2}>
                      <Box sx={{ 
                        bgcolor: 'rgba(255,255,255,0.2)', 
                        borderRadius: 2, 
                        p: 1.5,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                      }}>
                        <CameraAlt sx={{ fontSize: 28 }} />
                      </Box>
                      <Box>
                        <Typography variant="body2" sx={{ opacity: 0.9, fontWeight: 500 }}>
                          Active Cameras
                        </Typography>
                        <Typography variant={isMobile ? "h5" : "h4"} sx={{ fontWeight: 700 }}>
                          {new Set(data.map(item => item.camera_id)).size}
                        </Typography>
                      </Box>
                    </Stack>
                  </CardContent>
                </Card>
              </Zoom>
            </Grid>
          </Grid>
        </Fade>

        {/* Images Grid */}
        {data.some(item => item.image_url) && (
          <Fade in timeout={2000}>
            <Paper sx={{ 
              p: { xs: 2, md: 3 }, 
              mb: 4, 
              borderRadius: 3,
              background: 'linear-gradient(145deg, #ffffff 0%, #f8fafc 100%)',
              border: '1px solid rgba(0,0,0,0.05)'
            }}>
              <Stack direction="row" alignItems="center" spacing={2} sx={{ mb: 3 }}>
                <Box sx={{ 
                  bgcolor: 'primary.main', 
                  borderRadius: 2, 
                  p: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <Visibility sx={{ color: 'white', fontSize: 24 }} />
                </Box>
                <Typography variant="h6" sx={{ fontWeight: 600, color: 'text.primary' }}>
                  Captured Images
                </Typography>
                <Badge 
                  badgeContent={data.filter(item => item.image_url).length} 
                  color="primary"
                  sx={{ ml: 'auto' }}
                />
              </Stack>
              
              <Box sx={{ maxHeight: { xs: 320, md: 520 }, overflowY: 'auto', pr: 1 }}>
                <ImageList 
                  cols={isMobile ? 2 : isTablet ? 3 : 4} 
                  rowHeight={isMobile ? 160 : 200}
                  gap={16}
                  sx={{ 
                    '& .MuiImageListItem-root': {
                      borderRadius: 2,
                      overflow: 'hidden',
                      boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
                      transition: 'transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out',
                      '&:hover': {
                        transform: 'translateY(-4px)',
                        boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
                      }
                    }
                  }}
                >
                  {data
                    .filter(item => item.image_url)
                    .map((item, index) => (
                      <ImageListItem key={index}>
                        <img
                          src={item.image_url}
                          alt={`Camera ${item.camera_id}`}
                          loading="lazy"
                          style={{ 
                            cursor: 'pointer',
                            width: '100%',
                            height: '100%',
                            objectFit: 'cover'
                          }}
                          onClick={() => handleImageClick(item.image_url)}
                        />
                        <ImageListItemBar
                          title={
                            <Stack direction="row" alignItems="center" spacing={1}>
                              <CameraAlt sx={{ fontSize: 16 }} />
                              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                                Camera: {item.camera_id}
                              </Typography>
                              {hasSeatNumber && item.seat_number !== undefined && item.seat_number !== null && item.seat_number !== '' && (
                                <>
                                  <Typography variant="body2" sx={{ fontWeight: 600 }}>|</Typography>
                                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                                    Seat: {item.seat_number}
                                  </Typography>
                                </>
                              )}
                            </Stack>
                          }
                          subtitle={
                            <Stack spacing={0.5}>
                              <Typography variant="caption" sx={{ opacity: 0.9 }}>
                                {item.created_at ? 
                                  format(new Date(item.created_at.seconds * 1000), 'MMM dd, HH:mm') :
                                  item.timestamp
                                }
                              </Typography>
                              <Chip
                                label={getActionFromData(item)}
                                size="small"
                                color={getActionSeverity(item)}
                                sx={{ 
                                  fontSize: '0.7rem',
                                  height: 20,
                                  '& .MuiChip-label': { px: 1 }
                                }}
                              />
                            </Stack>
                          }
                          actionIcon={
                            <Tooltip title="View Full Size">
                              <IconButton
                                sx={{ 
                                  color: 'rgba(255, 255, 255, 0.8)',
                                  bgcolor: 'rgba(0,0,0,0.3)',
                                  '&:hover': {
                                    bgcolor: 'rgba(0,0,0,0.5)',
                                    color: 'white'
                                  }
                                }}
                                onClick={() => handleImageClick(item.image_url)}
                              >
                                <Visibility />
                              </IconButton>
                            </Tooltip>
                          }
                          sx={{
                            background: 'linear-gradient(to top, rgba(0,0,0,0.7) 0%, rgba(0,0,0,0.3) 70%, rgba(0,0,0,0) 100%)',
                            '& .MuiImageListItemBar-title': {
                              color: 'white',
                              fontWeight: 600
                            },
                            '& .MuiImageListItemBar-subtitle': {
                              color: 'rgba(255,255,255,0.9)'
                            }
                          }}
                        />
                      </ImageListItem>
                    ))}
                </ImageList>
              </Box>
            </Paper>
          </Fade>
        )}

        {/* Data Table */}
        <Fade in timeout={2200}>
          <Paper sx={{ 
            width: '100%', 
            overflow: 'hidden',
            borderRadius: 3,
            background: 'linear-gradient(145deg, #ffffff 0%, #f8fafc 100%)',
            border: '1px solid rgba(0,0,0,0.05)'
          }}>
            <Box sx={{ p: 3, borderBottom: '1px solid rgba(0,0,0,0.05)' }}>
              <Stack direction="row" alignItems="center" spacing={2}>
                <Box sx={{ 
                  bgcolor: 'primary.main', 
                  borderRadius: 2, 
                  p: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <Sensors sx={{ color: 'white', fontSize: 24 }} />
                </Box>
                <Typography variant="h6" sx={{ fontWeight: 600, color: 'text.primary' }}>
                  Detailed Records
                </Typography>
              </Stack>
            </Box>
            
            <TableContainer sx={{ maxHeight: { xs: 400, md: 600 } }}>
              <Table stickyHeader>
                <TableHead>
                  <TableRow sx={{ bgcolor: 'grey.50' }}>
                    <TableCell sx={{ fontWeight: 600, fontSize: '0.875rem' }}>
                      <Stack direction="row" alignItems="center" spacing={1}>
                        <AccessTime sx={{ fontSize: 16 }} />
                        <span>Timestamp</span>
                      </Stack>
                    </TableCell>
                    <TableCell sx={{ fontWeight: 600, fontSize: '0.875rem' }}>
                      <Stack direction="row" alignItems="center" spacing={1}>
                        <CameraAlt sx={{ fontSize: 16 }} />
                        <span>Camera</span>
                      </Stack>
                    </TableCell>
                  {hasSeatNumber && (
                    <TableCell sx={{ fontWeight: 600, fontSize: '0.875rem' }}>
                      <Stack direction="row" alignItems="center" spacing={1}>
                        <Person sx={{ fontSize: 16 }} />
                        <span>Seat</span>
                      </Stack>
                    </TableCell>
                  )}
                    <TableCell sx={{ fontWeight: 600, fontSize: '0.875rem' }}>
                      <Stack direction="row" alignItems="center" spacing={1}>
                        <Warning sx={{ fontSize: 16 }} />
                        <span>Events</span>
                      </Stack>
                    </TableCell>
                    <TableCell sx={{ fontWeight: 600, fontSize: '0.875rem' }}>
                      <Stack direction="row" alignItems="center" spacing={1}>
                        <Person sx={{ fontSize: 16 }} />
                        <span>Unknown</span>
                      </Stack>
                    </TableCell>
                    {!isMobile && (
                      <>
                        <TableCell sx={{ fontWeight: 600, fontSize: '0.875rem' }}>Faces</TableCell>
                        <TableCell sx={{ fontWeight: 600, fontSize: '0.875rem' }}>Sensors</TableCell>
                        <TableCell sx={{ fontWeight: 600, fontSize: '0.875rem' }}>Angle</TableCell>
                        <TableCell sx={{ fontWeight: 600, fontSize: '0.875rem' }}>
                          <Stack direction="row" alignItems="center" spacing={1}>
                            <LocationOn sx={{ fontSize: 16 }} />
                            <span>Location</span>
                          </Stack>
                        </TableCell>
                        <TableCell sx={{ fontWeight: 600, fontSize: '0.875rem' }}>
                          <Stack direction="row" alignItems="center" spacing={1}>
                            <Language sx={{ fontSize: 16 }} />
                            <span>Lang</span>
                          </Stack>
                        </TableCell>
                      </>
                    )}
                    <TableCell sx={{ fontWeight: 600, fontSize: '0.875rem' }}>Image</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.map((item, index) => (
                    <TableRow 
                      key={index} 
                      hover
                      sx={{ 
                        '&:nth-of-type(odd)': { bgcolor: 'rgba(0,0,0,0.02)' },
                        '&:hover': { bgcolor: 'rgba(37, 99, 235, 0.04)' }
                      }}
                    >
                      <TableCell sx={{ fontSize: '0.875rem' }}>
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                          {item.created_at ? 
                            format(new Date(item.created_at.seconds * 1000), 'MMM dd, HH:mm') :
                            item.timestamp
                          }
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip 
                          label={item.camera_id} 
                          color="primary" 
                          size="small"
                          sx={{ fontWeight: 600 }}
                        />
                      </TableCell>
                      {hasSeatNumber && (
                        <TableCell>
                          {item.seat_number !== undefined && item.seat_number !== null && item.seat_number !== '' ? (
                            <Chip 
                              label={item.seat_number}
                              color="secondary"
                              size="small"
                              sx={{ fontWeight: 600 }}
                            />
                          ) : (
                            <Typography variant="body2" color="text.secondary">Old Data</Typography>
                          )}
                        </TableCell>
                      )}
                      <TableCell>
                        <Stack direction="row" flexWrap="wrap" spacing={0.5}>
                          {item.events?.slice(0, isMobile ? 1 : 2).map((event, eventIndex) => (
                            <Chip
                              key={eventIndex}
                              label={isMobile ? event.split(' ')[0] : event}
                              color={getEventChipColor(event)}
                              size="small"
                              icon={getEventIcon(event)}
                              sx={{ 
                                fontSize: '0.7rem',
                                height: 24,
                                '& .MuiChip-icon': { fontSize: 14 }
                              }}
                            />
                          ))}
                          {item.events?.length > (isMobile ? 1 : 2) && (
                            <Chip
                              label={`+${item.events.length - (isMobile ? 1 : 2)}`}
                              size="small"
                              sx={{ fontSize: '0.7rem', height: 24 }}
                            />
                          )}
                        </Stack>
                      </TableCell>
                      <TableCell>
                        <Typography 
                          color={item.unknown_faces > 0 ? 'error' : 'textPrimary'}
                          sx={{ fontWeight: item.unknown_faces > 0 ? 600 : 400 }}
                        >
                          {item.unknown_faces || 0}
                        </Typography>
                      </TableCell>
                      {!isMobile && (
                        <>
                          <TableCell>
                            <Typography variant="body2">
                              {item.faces_detected?.length || 0}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Stack spacing={0.5}>
                              {item.sensor_readings?.slice(0, 2).map((reading, readingIndex) => (
                                <Typography key={readingIndex} variant="caption" display="block">
                                  S{readingIndex + 1}: {reading}
                                </Typography>
                              ))}
                            </Stack>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">
                              {item.angle || 0}°
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" color="text.secondary">
                              {item.location || 'Unknown'}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip 
                              label={item.language || 'en'} 
                              size="small"
                              variant="outlined"
                            />
                          </TableCell>
                        </>
                      )}
                      <TableCell>
                        {item.image_url && (
                          <Button
                            size="small"
                            startIcon={<Visibility />}
                            onClick={() => handleImageClick(item.image_url)}
                            sx={{ 
                              textTransform: 'none',
                              fontWeight: 600,
                              borderRadius: 2
                            }}
                          >
                            {isMobile ? 'View' : 'View Image'}
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </Fade>

        {/* Image Dialog */}
        <Dialog
          open={imageDialogOpen}
          onClose={handleCloseImageDialog}
          maxWidth="lg"
          fullWidth
          fullScreen={isMobile}
          PaperProps={{
            sx: {
              borderRadius: isMobile ? 0 : 3,
              maxHeight: '90vh'
            }
          }}
        >
          <DialogTitle sx={{ 
            pb: 1,
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            color: 'white',
            position: 'relative'
          }}>
            <Stack direction="row" alignItems="center" spacing={2}>
              <CameraAlt sx={{ fontSize: 28 }} />
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                Full Size Image
              </Typography>
            </Stack>
            <IconButton
              aria-label="close"
              onClick={handleCloseImageDialog}
              sx={{ 
                position: 'absolute', 
                right: 16, 
                top: 16,
                color: 'white',
                bgcolor: 'rgba(255,255,255,0.2)',
                '&:hover': {
                  bgcolor: 'rgba(255,255,255,0.3)'
                }
              }}
            >
              <Close />
            </IconButton>
          </DialogTitle>
          <DialogContent sx={{ p: 0, bgcolor: 'grey.100' }}>
            {selectedImage && (
              <Box sx={{ 
                display: 'flex', 
                justifyContent: 'center', 
                alignItems: 'center',
                minHeight: isMobile ? '60vh' : '70vh',
                p: 2
              }}>
                <img
                  src={selectedImage}
                  alt="Full size"
                  style={{ 
                    width: '100%', 
                    height: 'auto',
                    maxHeight: isMobile ? '60vh' : '70vh',
                    objectFit: 'contain',
                    borderRadius: 8,
                    boxShadow: '0 10px 25px -5px rgb(0 0 0 / 0.1), 0 4px 6px -2px rgb(0 0 0 / 0.05)'
                  }}
                />
              </Box>
            )}
          </DialogContent>
          <DialogActions sx={{ 
            p: 3, 
            bgcolor: 'background.paper',
            borderTop: '1px solid rgba(0,0,0,0.05)'
          }}>
            <Button 
              onClick={handleCloseImageDialog}
              variant="contained"
              sx={{ 
                borderRadius: 2,
                textTransform: 'none',
                fontWeight: 600,
                px: 4
              }}
            >
              Close
            </Button>
          </DialogActions>
        </Dialog>
      </Container>
    </Box>
  );
};

export default Dashboard;
